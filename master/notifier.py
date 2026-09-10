import os
import re
import sys
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

log = logging.getLogger(__name__)

# ── Valid notification channels ───────────────────────────────────────────────
VALID_CHANNELS = {"telegram", "gmail", "office365", "viber"}


def _parse_channels() -> list[str]:
    """Read NOTIFY_CHANNELS from .env and return a filtered list of valid channels."""
    raw = os.environ.get("NOTIFY_CHANNELS", os.environ.get("NOTIFY_CHANNEL", "telegram"))
    channels = [c.strip().lower() for c in raw.split(",") if c.strip()]
    valid    = [c for c in channels if c in VALID_CHANNELS]
    invalid  = [c for c in channels if c not in VALID_CHANNELS]
    if invalid:
        log.warning(f"Invalid channels ignored: {invalid}. Valid options: {VALID_CHANNELS}")
    if not valid:
        log.warning("No valid channels configured. Falling back to: telegram")
        return ["telegram"]
    return valid


class Notifier:
    def __init__(self):
        self.channels = _parse_channels()
        log.info(f"Active notification channels: {', '.join(self.channels)}")

        # --- Telegram ---
        self.tg_bot_token = os.environ.get("TG_BOT_TOKEN", "")
        self.tg_chat_id   = os.environ.get("TG_CHAT_ID", "")

        # --- Viber ---
        self.viber_auth_token  = os.environ.get("VIBER_AUTH_TOKEN", "")
        self.viber_receiver_id = os.environ.get("VIBER_RECEIVER_ID", "")
        self.viber_bot_name    = os.environ.get("VIBER_BOT_NAME", "Linux Monitor")

        # --- Gmail ---
        self.gmail_user = os.environ.get("GMAIL_USER", "")
        self.gmail_pass = os.environ.get("GMAIL_APP_PASS", "")
        self.gmail_to   = os.environ.get("GMAIL_TO", "")

        # --- Office 365 ---
        self.o365_user      = os.environ.get("O365_USER", "")
        self.o365_pass      = os.environ.get("O365_PASS", "")
        self.o365_mail_to   = os.environ.get("MAIL_TO", "")
        self.o365_mail_from = os.environ.get("MAIL_FROM", self.o365_user)

        # Map channel name → handler function
        self._dispatch = {
            "telegram":  self._send_telegram,
            "gmail":     self._send_gmail,
            "office365": self._send_office365,
            "viber":     self._send_viber,
        }

    # ── Public ────────────────────────────────────────────────────────────── #

    def send_alert(self, message: str):
        """Send an alert to ALL channels configured in NOTIFY_CHANNELS."""
        errors = []
        for channel in self.channels:
            handler = self._dispatch.get(channel)
            if handler:
                try:
                    handler(message)
                except Exception as e:
                    err = f"[{channel}] {e}"
                    log.error(err)
                    errors.append(err)
        if errors:
            log.error(f"Some channels failed to send: {errors}")

    # ── Telegram ──────────────────────────────────────────────────────────── #

    def _send_telegram(self, message: str):
        if not self.tg_bot_token or not self.tg_chat_id:
            log.warning("[Telegram] TG_BOT_TOKEN or TG_CHAT_ID is not configured in .env.")
            return
        url     = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        resp    = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            log.info("[Telegram] ✅ Alert sent successfully.")
        else:
            log.error(f"[Telegram] ❌ HTTP error {resp.status_code}: {resp.text}")

    # ── Gmail ─────────────────────────────────────────────────────────────── #

    def _send_gmail(self, message: str):
        if not self.gmail_user or not self.gmail_pass or not self.gmail_to:
            log.warning("[Gmail] GMAIL_USER, GMAIL_APP_PASS or GMAIL_TO is not configured in .env.")
            return
        msg = self._build_email_msg(
            subject=self._extract_subject(message),
            from_addr=f"Linux Monitor <{self.gmail_user}>",
            to_addr=self.gmail_to,
            plain=self._strip_html(message),
            html=self._wrap_html_email(message),
        )
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
                s.ehlo(); s.starttls()
                s.login(self.gmail_user, self.gmail_pass)
                s.sendmail(self.gmail_user, self.gmail_to.split(","), msg.as_string())
            log.info(f"[Gmail] ✅ Alert sent successfully to {self.gmail_to}")
        except smtplib.SMTPAuthenticationError:
            log.error("[Gmail] ❌ Authentication failed. Check GMAIL_USER & GMAIL_APP_PASS.")

    # ── Office 365 ────────────────────────────────────────────────────────── #

    def _send_office365(self, message: str):
        if not self.o365_user or not self.o365_pass or not self.o365_mail_to:
            log.warning("[Office365] O365_USER, O365_PASS or MAIL_TO is not configured in .env.")
            return
        msg = self._build_email_msg(
            subject=self._extract_subject(message),
            from_addr=self.o365_mail_from,
            to_addr=self.o365_mail_to,
            plain=self._strip_html(message),
            html=self._wrap_html_email(message),
        )
        try:
            with smtplib.SMTP("smtp.office365.com", 587, timeout=15) as s:
                s.ehlo(); s.starttls()
                s.login(self.o365_user, self.o365_pass)
                s.sendmail(self.o365_mail_from, self.o365_mail_to.split(","), msg.as_string())
            log.info(f"[Office365] ✅ Alert sent successfully to {self.o365_mail_to}")
        except smtplib.SMTPAuthenticationError:
            log.error("[Office365] ❌ Authentication failed. Check O365_USER & O365_PASS.")

    # ── Viber ─────────────────────────────────────────────────────────────── #

    def _send_viber(self, message: str):
        if not self.viber_auth_token or not self.viber_receiver_id:
            log.warning("[Viber] VIBER_AUTH_TOKEN or VIBER_RECEIVER_ID is not configured in .env.")
            return
        url     = "https://chatapi.viber.com/pa/send_message"
        headers = {"X-Viber-Auth-Token": self.viber_auth_token}
        payload = {
            "receiver":        self.viber_receiver_id,
            "min_api_version": 1,
            "sender":          {"name": self.viber_bot_name},
            "tracking_data":   "monitor_alert",
            "type":            "text",
            "text":            self._strip_html(message),   # Viber accepts plain text only
        }
        resp      = requests.post(url, json=payload, headers=headers, timeout=5)
        resp_data = resp.json()
        if resp_data.get("status") == 0:
            log.info("[Viber] ✅ Alert sent successfully.")
        else:
            log.error(f"[Viber] ❌ Error: {resp_data.get('status_message')}")

    # ── Helpers ───────────────────────────────────────────────────────────── #

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def _extract_subject(message: str) -> str:
        first = message.strip().splitlines()[0] if message.strip() else "Linux Monitor Alert"
        return re.sub(r"<[^>]+>", "", first)[:100]

    @staticmethod
    def _build_email_msg(subject, from_addr, to_addr, plain, html) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = from_addr
        msg["To"]      = to_addr
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html,  "html",  "utf-8"))
        return msg

    @staticmethod
    def _wrap_html_email(message: str) -> str:
        body = message.replace("\n", "<br>")
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Courier New', monospace; background:#1e1e2e; color:#cdd6f4; padding:20px; margin:0; }}
    .card {{ background:#313244; border-radius:10px; padding:24px; max-width:620px; margin:auto; box-shadow:0 4px 20px rgba(0,0,0,.4); }}
    pre  {{ background:#181825; padding:14px; border-radius:6px; overflow-x:auto; font-size:13px; }}
    code {{ background:#181825; padding:2px 6px; border-radius:4px; color:#f38ba8; }}
    b    {{ color:#cba6f7; }}
    i    {{ color:#a6e3a1; font-style:italic; }}
    .footer {{ color:#585b70; font-size:11px; margin-top:16px; text-align:center; }}
    hr   {{ border:none; border-top:1px solid #45475a; margin:16px 0; }}
  </style>
</head>
<body>
  <div class="card">
    {body}
    <hr>
    <p class="footer">🤖 Powered by Linux Monitor System</p>
  </div>
</body>
</html>"""
