"""
BlockRun Model Integration v3 - MIT PROMPT CACHING
===================================================

NEU: Unterstützt Anthropic Prompt Caching für 90% Kostenersparnis!
"""

import json
import logging
import os
from typing import Any, List, Optional

import httpx
from eth_account import Account
from blockrun_llm.x402 import create_payment_payload, extract_payment_details, parse_payment_required

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from eli.config import settings
from eli.agent.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)

BLOCKRUN_API_URL = "https://blockrun.ai/api"


def _load_wallet() -> tuple[str, Account]:
    """Lädt Wallet und gibt (address, account) zurück."""
    wallet_file = settings.data_path / "wallet.json"
    if not wallet_file.exists():
        raise FileNotFoundError(
            "Wallet nicht gefunden. Generiere zuerst ein Wallet mit WalletManager."
        )

    with open(wallet_file) as f:
        data = json.load(f)

    private_key = data["private_key"]
    account = Account.from_key(private_key)

    return account.address, account


class ChatBlockRun(BaseChatModel):
    """
    LangChain ChatModel für BlockRun.ai mit x402 Payments und Prompt Caching.
    """

    model: str = "anthropic/claude-sonnet-4"
    max_tokens: int = 4096
    temperature: float = 1.0
    enable_caching: bool = True  # NEU: Prompt Caching aktivieren

    _wallet_address: str | None = None
    _account: Any = None
    _tools: list[dict] | None = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tools = None
        self._wallet_address = None
        self._account = None

    def _ensure_wallet(self):
        """Lazy-load Wallet."""
        if self._wallet_address is None:
            self._wallet_address, self._account = _load_wallet()
            logger.info(f"BlockRun Wallet geladen: {self._wallet_address}")

    @property
    def _llm_type(self) -> str:
        return "blockrun-x402-caching"

    @property
    def _identifying_params(self) -> dict:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "caching_enabled": self.enable_caching,
        }

    def bind_tools(self, tools: list) -> "ChatBlockRun":
        """Bindet Tools an das Model."""
        bound = ChatBlockRun(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            enable_caching=self.enable_caching,
        )

        # Tools in OpenAI Format konvertieren
        bound._tools = []
        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "description"):
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                    }
                }
                if hasattr(tool, "args_schema") and tool.args_schema:
                    tool_def["function"]["parameters"] = tool.args_schema.model_json_schema()
                bound._tools.append(tool_def)
            elif isinstance(tool, dict):
                bound._tools.append(tool)

        return bound

    def _convert_messages(self, messages: List[BaseMessage]) -> tuple[list[dict] | None, list[dict]]:
        """
        Konvertiert LangChain Messages in Anthropic Format MIT Prompt Caching.
        
        Returns:
            (system_blocks, messages)
            system_blocks: List von System Message Blocks mit cache_control
            messages: Konvertierte User/Assistant Messages
        """
        system_blocks = []
        converted = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                # System Message als Anthropic block structure
                system_blocks.append({
                    "type": "text",
                    "text": msg.content
                })
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                ai_msg = {"role": "assistant", "content": msg.content or ""}
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    ai_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", tc.get("name", "")),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("args", {})),
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                converted.append(ai_msg)
            elif isinstance(msg, ToolMessage):
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

        # PROMPT CACHING: Cache Control auf letzten System Block setzen
        if self.enable_caching and system_blocks:
            system_blocks[-1]["cache_control"] = {"type": "ephemeral"}
            logger.debug("Prompt caching enabled for system prompt")

        return system_blocks if system_blocks else None, converted

    def _create_x402_payment(self, payment_info: dict, is_testnet: bool = False) -> str:
        """Erstellt x402 Payment Payload mit EIP-712 Signing."""
        self._ensure_wallet()

        if isinstance(payment_info, dict):
            payment_required = payment_info
        else:
            payment_required = parse_payment_required(payment_info)

        logger.info(f"=== x402 Payment Details ===")
        details = extract_payment_details(payment_required)
        
        network = "eip155:84532" if is_testnet else "eip155:8453"
        resource = details.get("resource") or {}
        extensions = payment_required.get("extensions", {})
        
        logger.info(f"Recipient: {details['recipient']}")
        logger.info(f"Amount: {details['amount']}")
        logger.info(f"Asset: {details.get('asset', 'N/A')}")

        payment_payload = create_payment_payload(
            account=self._account,
            recipient=details["recipient"],
            amount=details["amount"],
            network=network,
            resource_url=resource.get("url", f"{BLOCKRUN_API_URL}/v1/chat/completions"),
            resource_description=resource.get("description", "BlockRun AI API call"),
            max_timeout_seconds=details.get("maxTimeoutSeconds", 300),
            extra=details.get("extra"),
            extensions=extensions,
            asset=details.get("asset"),
        )

        logger.info(f"Payment payload created, length: {len(payment_payload)}")
        return payment_payload

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """Async Generation mit BlockRun REST API und Prompt Caching."""
        self._ensure_wallet()

        # Messages konvertieren (mit Caching Support)
        system_blocks, converted_messages = self._convert_messages(messages)

        # Request Body
        request_body = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        # System Blocks mit Cache Control hinzufügen
        if system_blocks:
            request_body["system"] = system_blocks

        # Tools hinzufügen wenn vorhanden
        if self._tools:
            request_body["tools"] = self._tools

        try:
            async with httpx.AsyncClient() as client:
                # Initial Request
                response = await client.post(
                    f"{BLOCKRUN_API_URL}/v1/chat/completions",
                    json=request_body,
                    timeout=60.0
                )

                # 402 Payment Required
                if response.status_code == 402:
                    payment_header = response.headers.get("x-payment-required") or response.headers.get("payment-required")
                    if not payment_header:
                        raise ValueError("No payment header in 402 response")
                    
                    payment_info = parse_payment_required(payment_header)
                    price_info = response.json()
                    logger.info(f"x402 Payment Required: ${price_info.get('price', {}).get('amount', '?')}")

                    payment_payload = self._create_x402_payment(payment_info)
                    
                    logger.info("Sending request WITH payment signature...")
                    response = await client.post(
                        f"{BLOCKRUN_API_URL}/v1/chat/completions",
                        json=request_body,
                        headers={
                            "Content-Type": "application/json",
                            "PAYMENT-SIGNATURE": payment_payload,
                        },
                        timeout=60.0
                    )

                    logger.info(f"Payment response status: {response.status_code}")
                    if response.status_code == 200:
                        logger.info("Payment ACCEPTED! API call successful.")

                # Response parsen
                if response.status_code == 200:
                    result = response.json()

                    if "choices" in result and result["choices"]:
                        choice = result["choices"][0]
                        message = choice["message"]
                        content = message.get("content", "")

                        ai_message = AIMessage(content=content or "")

                        if "tool_calls" in message:
                            ai_message.tool_calls = [
                                {
                                    "id": tc["id"],
                                    "name": tc["function"]["name"],
                                    "args": json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {},
                                }
                                for tc in message["tool_calls"]
                            ]

                        # COST TRACKING + Usage loggen
                        if "usage" in result:
                            usage = result["usage"]
                            prompt_tokens = usage.get("input_tokens", 0)
                            completion_tokens = usage.get("output_tokens", 0)
                            cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
                            cache_read_tokens = usage.get("cache_read_input_tokens", 0)

                            logger.info(
                                f"BlockRun Usage: {prompt_tokens} prompt, "
                                f"{completion_tokens} completion, "
                                f"{cache_creation_tokens} cache_write, "
                                f"{cache_read_tokens} cache_read tokens"
                            )

                            # Cost berechnen und tracken
                            cost_usd = cost_tracker.calculate_cost(
                                model=self.model,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                cache_creation_tokens=cache_creation_tokens,
                                cache_read_tokens=cache_read_tokens,
                            )

                            cost_tracker.log_request(
                                model=self.model,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                cache_creation_tokens=cache_creation_tokens,
                                cache_read_tokens=cache_read_tokens,
                                cost_usd=cost_usd,
                                context=kwargs.get("context", {}),
                            )

                            logger.info(f"Estimated cost: ${cost_usd:.6f}")

                        return ChatResult(
                            generations=[ChatGeneration(message=ai_message)],
                        )
                    else:
                        raise ValueError(f"Unexpected response format: {result}")
                else:
                    raise ValueError(f"BlockRun API Error {response.status_code}: {response.text}")

        except Exception as e:
            error_str = str(e).lower()
            if "insufficient" in error_str or "balance" in error_str or "usdc" in error_str:
                from eli.agent.graph import InsufficientFundsError
                raise InsufficientFundsError(f"Nicht genug USDC: {e}") from e
            logger.error(f"BlockRun API Fehler: {e}")
            raise

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """Sync Generation."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._agenerate(messages, stop, run_manager, **kwargs)
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(self._agenerate(messages, stop, run_manager, **kwargs))


def create_blockrun_model(
    model: str = "anthropic/claude-sonnet-4",
    max_tokens: int = 4096,
    enable_caching: bool = True,
) -> ChatBlockRun:
    """Factory-Funktion für BlockRun Model mit Prompt Caching."""
    return ChatBlockRun(
        model=model,
        max_tokens=max_tokens,
        enable_caching=enable_caching,
    )
