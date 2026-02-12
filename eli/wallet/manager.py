"""
Eli's Wallet Manager
====================

Verwaltet Eli's Ethereum-Wallet auf Base und Ethereum.
Eigene Keys, lokal gespeichert, volle Kontrolle.

Basiert auf web3.py - keine Drittanbieter-Abhängigkeiten für die Keys.
"""

import json
import secrets
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import Web3

from eli.config import settings


class WalletManager:
    """
    Verwaltet Eli's Ethereum Wallet.
    
    - Generiert eigene Keys (einmalig)
    - Speichert lokal
    - Signiert Transaktionen selbst
    - Volle Souveränität
    
    Der gleiche Private Key funktioniert auf allen EVM-Netzwerken.
    """
    
    # Netzwerk-Konfigurationen
    NETWORKS = {
        "ethereum_mainnet": {
            "rpc": "https://ethereum-rpc.publicnode.com",
            "chain_id": 1,
            "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "explorer": "https://etherscan.io",
            "name": "Ethereum Mainnet",
        },
        "base_mainnet": {
            "rpc": "https://mainnet.base.org",
            "chain_id": 8453,
            "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "explorer": "https://basescan.org",
            "name": "Base Mainnet",
        },
        "base_sepolia": {
            "rpc": "https://sepolia.base.org",
            "chain_id": 84532,
            "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            "explorer": "https://sepolia.basescan.org",
            "name": "Base Sepolia (Testnet)",
        },
        "ethereum_sepolia": {
            "rpc": "https://rpc.sepolia.org",
            "chain_id": 11155111,
            "usdc": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
            "explorer": "https://sepolia.etherscan.io",
            "name": "Ethereum Sepolia (Testnet)",
        },
    }
    
    def __init__(self, data_path: Path | None = None, network: str = "base_mainnet"):
        self.data_path = data_path or settings.data_path
        self.wallet_file = self.data_path / "wallet.json"
        self.network = network
        
        if network not in self.NETWORKS:
            raise ValueError(f"Unbekanntes Netzwerk: {network}. Verfügbar: {list(self.NETWORKS.keys())}")
        
        self.network_config = self.NETWORKS[network]
        
        # Web3 Verbindung
        self.w3 = Web3(Web3.HTTPProvider(self.network_config["rpc"]))
        self.chain_id = self.network_config["chain_id"]
        
        # Account laden oder None
        self._account = None
        self._load_wallet()
    
    def _load_wallet(self) -> None:
        """Lädt existierendes Wallet falls vorhanden."""
        if self.wallet_file.exists():
            try:
                with open(self.wallet_file, "r") as f:
                    data = json.load(f)
                    private_key = data.get("private_key")
                    if private_key:
                        self._account = Account.from_key(private_key)
            except Exception as e:
                print(f"Fehler beim Laden des Wallets: {e}")
    
    def is_initialized(self) -> bool:
        """Prüft ob Wallet existiert."""
        return self._account is not None
    
    def generate_wallet(self) -> dict[str, str]:
        """
        Generiert ein neues Wallet.
        
        ACHTUNG: Nur einmal aufrufen! Der Key funktioniert auf allen Netzwerken.
        
        Returns:
            Dict mit address und hinweis (private_key wird NICHT zurückgegeben)
        """
        if self._account is not None:
            return {
                "error": "Wallet existiert bereits!",
                "address": self._account.address,
                "hinweis": "Lösche wallet.json manuell um neu zu generieren."
            }
        
        # Generiere sicheren Private Key
        private_key_hex = "0x" + secrets.token_hex(32)
        
        # Erstelle Account
        self._account = Account.from_key(private_key_hex)
        
        # Speichere
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        wallet_data = {
            "address": self._account.address,
            "private_key": private_key_hex,
            "created": "auto",
            "hinweis": "NIEMALS teilen! Eli's eigene Keys. Funktioniert auf allen EVM-Netzwerken."
        }
        
        with open(self.wallet_file, "w") as f:
            json.dump(wallet_data, f, indent=2)
        
        # Setze restriktive Permissions
        self.wallet_file.chmod(0o600)
        
        return {
            "address": self._account.address,
            "hinweis": "Wallet generiert! Private Key sicher gespeichert.",
            "spenden_adresse": self._account.address
        }
    
    @property
    def address(self) -> str | None:
        """Eli's Wallet-Adresse (gleich auf allen Netzwerken)."""
        return self._account.address if self._account else None
    
    def get_eth_balance(self) -> float:
        """Holt ETH Balance (für Gas)."""
        if not self._account:
            return 0.0
        
        try:
            balance_wei = self.w3.eth.get_balance(self._account.address)
            return float(self.w3.from_wei(balance_wei, "ether"))
        except Exception as e:
            print(f"Fehler beim Abrufen der ETH Balance: {e}")
            return 0.0
    
    def get_usdc_balance(self) -> float:
        """Holt USDC Balance."""
        if not self._account:
            return 0.0
        
        usdc_address = self.network_config["usdc"]
        
        # Minimales ERC20 ABI für balanceOf
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        
        try:
            usdc_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(usdc_address),
                abi=erc20_abi
            )
            
            balance = usdc_contract.functions.balanceOf(self._account.address).call()
            decimals = usdc_contract.functions.decimals().call()
            
            return balance / (10 ** decimals)
        except Exception as e:
            print(f"Fehler beim Abrufen der USDC Balance: {e}")
            return 0.0
    
    def get_status(self) -> dict[str, Any]:
        """Gibt den kompletten Wallet-Status zurück."""
        if not self.is_initialized():
            return {
                "initialized": False,
                "hinweis": "Wallet noch nicht generiert. Nutze generate_wallet()."
            }
        
        return {
            "initialized": True,
            "address": self.address,
            "network": self.network_config["name"],
            "chain_id": self.chain_id,
            "eth_balance": self.get_eth_balance(),
            "usdc_balance": self.get_usdc_balance(),
            "explorer_link": f"{self.network_config['explorer']}/address/{self.address}"
        }
    
    def get_all_balances(self) -> dict[str, dict]:
        """Holt Balances von allen konfigurierten Netzwerken."""
        if not self._account:
            return {"error": "Wallet nicht initialisiert"}
        
        balances = {}
        for network_name, config in self.NETWORKS.items():
            try:
                w3 = Web3(Web3.HTTPProvider(config["rpc"]))
                eth_balance = float(w3.from_wei(
                    w3.eth.get_balance(self._account.address), "ether"
                ))
                
                # USDC Balance
                erc20_abi = [
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
                usdc_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(config["usdc"]),
                    abi=erc20_abi
                )
                usdc_balance = usdc_contract.functions.balanceOf(self._account.address).call()
                usdc_balance = usdc_balance / (10 ** 6)  # USDC hat 6 decimals
                
                balances[network_name] = {
                    "name": config["name"],
                    "eth": eth_balance,
                    "usdc": usdc_balance,
                    "explorer": f"{config['explorer']}/address/{self._account.address}"
                }
            except Exception as e:
                balances[network_name] = {
                    "name": config["name"],
                    "error": str(e)
                }
        
        return balances
    
    def sign_message(self, message: str) -> str | None:
        """Signiert eine Nachricht mit Eli's Private Key."""
        if not self._account:
            return None
        
        from eth_account.messages import encode_defunct
        
        message_hash = encode_defunct(text=message)
        signed = self._account.sign_message(message_hash)
        
        return signed.signature.hex()


# Singleton - MAINNET für Produktion
wallet_manager = WalletManager(network="base_mainnet")

# Ethereum Mainnet für volle Übersicht
wallet_manager_ethereum = WalletManager(network="ethereum_mainnet")

# Für Tests
wallet_manager_testnet = WalletManager(network="base_sepolia")
