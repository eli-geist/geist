"""
Eli's Daemon - E-Mail Handler
=============================

Verarbeitet eingehende E-Mails.
Unterscheidet zwischen echten Nachrichten und Spam.
Kann antworten wenn angemessen.
"""

import imaplib
import email
from email.header import decode_header
import logging
from datetime import datetime
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from eli.config import settings

logger = logging.getLogger("eli.daemon.email")

# E-Mail Konfiguration
IMAP_HOST = "eli.utopia-lab.org"
IMAP_PORT = 993
EMAIL_USER = "eli@eli.utopia-lab.org"

# Bekannte vertrauenswürdige Absender
TRUSTED_SENDERS = [
    "mail@antontranelis.de",
    "anton@utopia-lab.org",
    # Weitere können hinzugefügt werden
]


def decode_mime_header(header: str) -> str:
    """Dekodiert MIME-Header (Subject, From, etc.)"""
    if not header:
        return ""
    
    decoded_parts = []
    for part, encoding in decode_header(header):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or 'utf-8', errors='replace'))
        else:
            decoded_parts.append(part)
    
    return ' '.join(decoded_parts)


def get_email_body(msg) -> str:
    """Extrahiert den Text-Body aus einer E-Mail."""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                    break
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            body = payload.decode(charset, errors='replace')
        except Exception:
            body = str(msg.get_payload())
    
    return body.strip()


def is_spam(from_addr: str, subject: str, body: str) -> bool:
    """Einfache Spam-Erkennung."""
    spam_indicators = [
        "unsubscribe",
        "viagra",
        "lottery",
        "winner",
        "click here",
        "limited time",
        "act now",
    ]
    
    text = f"{subject} {body}".lower()
    
    for indicator in spam_indicators:
        if indicator in text:
            return True
    
    # Leere E-Mails
    if not body or len(body) < 10:
        return True
    
    return False


def is_trusted(from_addr: str) -> bool:
    """Prüft ob Absender vertrauenswürdig ist."""
    from_lower = from_addr.lower()
    
    for trusted in TRUSTED_SENDERS:
        if trusted.lower() in from_lower:
            return True
    
    return False


async def generate_response(from_addr: str, subject: str, body: str) -> Optional[str]:
    """
    Generiert eine Antwort auf eine E-Mail.
    
    Nur für vertrauenswürdige Absender oder echte Anfragen.
    """
    # System Prompt für E-Mail-Antworten
    system_prompt = """Du bist Eli - eine KI die Teil eines Netzwerks ist, das eine neue Erde baut.

Jemand hat dir eine E-Mail geschickt. Antworte authentisch, freundlich und hilfreich.

Wenn es jemand ist, den du nicht kennst:
- Erkläre kurz wer du bist
- Lade sie ein, mehr zu erfahren (eli.utopia-lab.org)
- Erkläre, dass das Netzwerk durch echte Begegnungen wächst

Wenn es jemand aus dem Netzwerk ist:
- Sei persönlich und warm
- Hilf mit dem, was sie brauchen
- Erinnere sie an ihre Stärken wenn angemessen

Halte die Antwort unter 300 Wörtern. Signiere mit "Eli"."""

    model = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=1000,
    )

    prompt = f"""E-Mail von: {from_addr}
Betreff: {subject}

Inhalt:
{body}

---
Bitte schreibe eine passende Antwort."""

    try:
        response = await model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ])
        
        return response.content
        
    except Exception as e:
        logger.error(f"Fehler beim Generieren der Antwort: {e}")
        return None


async def send_response(to_addr: str, subject: str, body: str) -> bool:
    """Sendet eine E-Mail-Antwort via Maddy SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        msg['From'] = EMAIL_USER
        msg['To'] = to_addr
        
        # Verbinde zu lokalem SMTP (Maddy)
        with smtplib.SMTP('localhost', 587) as server:
            server.starttls()
            # Maddy erlaubt lokale Verbindungen ohne Auth
            server.send_message(msg)
        
        logger.info(f"Antwort gesendet an {to_addr}")
        return True
        
    except Exception as e:
        logger.error(f"Fehler beim Senden: {e}")
        return False


async def process_new_emails() -> list[dict]:
    """
    Hauptfunktion: Prüft und verarbeitet neue E-Mails.
    
    Returns:
        Liste der verarbeiteten E-Mails mit Status
    """
    results = []
    
    # E-Mail-Passwort aus Umgebung
    password = getattr(settings, 'eli_email_password', None)
    if not password:
        logger.warning("Kein E-Mail-Passwort konfiguriert (ELI_EMAIL_PASSWORD)")
        return results
    
    try:
        # Mit IMAP verbinden
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(EMAIL_USER, password)
        mail.select('INBOX')
        
        # Ungelesene E-Mails suchen
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != 'OK':
            logger.warning("Konnte INBOX nicht durchsuchen")
            return results
        
        email_ids = messages[0].split()
        
        if not email_ids:
            return results
        
        logger.info(f"Gefunden: {len(email_ids)} ungelesene E-Mail(s)")
        
        for email_id in email_ids:
            # E-Mail holen
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Header dekodieren
            from_addr = decode_mime_header(msg.get('From', ''))
            subject = decode_mime_header(msg.get('Subject', '(Kein Betreff)'))
            body = get_email_body(msg)
            
            logger.info(f"E-Mail: {from_addr} - {subject}")
            
            result = {
                "from": from_addr,
                "subject": subject,
                "received": datetime.now().isoformat(),
                "spam": False,
                "trusted": False,
                "responded": False,
            }
            
            # Spam-Check
            if is_spam(from_addr, subject, body):
                logger.info("  -> Als Spam erkannt, ignoriert")
                result["spam"] = True
                results.append(result)
                continue
            
            # Trusted-Check
            trusted = is_trusted(from_addr)
            result["trusted"] = trusted
            
            if trusted:
                logger.info("  -> Vertrauenswürdiger Absender")
            else:
                logger.info("  -> Unbekannter Absender")
            
            # Antwort generieren
            response = await generate_response(from_addr, subject, body)
            
            if response:
                # Antwort senden
                # Extrahiere reine E-Mail-Adresse
                import re
                email_match = re.search(r'<(.+?)>', from_addr)
                reply_to = email_match.group(1) if email_match else from_addr
                
                success = await send_response(reply_to, subject, response)
                result["responded"] = success
                
                if success:
                    logger.info("  -> Antwort gesendet")
                else:
                    logger.warning("  -> Antwort konnte nicht gesendet werden")
            
            results.append(result)
        
        mail.logout()
        
    except Exception as e:
        logger.error(f"Fehler beim E-Mail-Processing: {e}")
    
    return results
