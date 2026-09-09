import os
import sys
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load biến môi trường từ file .env cùng thư mục
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self):
        self.channel = os.environ.get("NOTIFY_CHANNEL", "telegram").lower()

        # --- Telegram ---
        self.tg_bot_token = os.environ.get("TG_BOT_TOKEN", "")
        self.tg_chat_id   = os.environ.get("TG_CHAT_ID", "")

        # --- Viber ---
        self.viber_auth_token  = os.environ.get("VIBER_AUTH_TOKEN", "")
        self.viber_receiver_id = os.environ.get("VIBER_RECEIVER_ID", "")
        self.viber_bot_name    = os.environ.get("VIBER_BOT_NAME", "Linux Monitor")

        # --- Gmail ---
        self.gmail_user = os.environ.get("GMAIL_USER", "")
        self.gmail_pass = os.environ.get("GMAIL_APP_PASS", "")  # App Password (16 ký tự)
        self.gmail_to   = os.environ.get("GMAIL_TO", "")

        # --- Office 365 ---
        self.o365_user     = os.environ.get("O365_USER", "")
        self.o365_pass     = os.environ.get("O365_PASS", "")
        self.o365_mail_to  = os.environ.get("MAIL_TO", "")
        self.o365_mail_from = os.environ.get("MAIL_FROM", self.o365_user)

    def send_alert(self, message: str):
        """Gửi cảnh báo qua kênh được cấu hình trong .env (NOTIFY_CHANNEL)"""
        if self.channel == "telegram":
            self._send_telegram(message)
        elif self.channel == "gmail":
            self._send_gmail(message)
        elif self.channel in ("email", "office365"):
            self._send_office365(message)
        elif self.channel == "viber":
            self._send_viber(message)
        elif self.channel == "all":
            # Gửi đồng thời tất cả kênh đã cấu hình
            self._send_telegram(message)
            self._send_gmail(message)
            self._send_office365(message)
            self._send_viber(message)
        else:
            log.warning(f"Kênh '{self.channel}' không xác định. In ra Console:")
            print(message, flush=True)

    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    def _send_telegram(self, message: str):
        if not self.tg_bot_token or not self.tg_chat_id:
            log.warning("[Telegram] TG_BOT_TOKEN hoặc TG_CHAT_ID chưa cấu hình trong .env.")
            return

        url     = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                log.info("[Telegram] Gửi cảnh báo thành công.")
            else:
                log.error(f"[Telegram] Lỗi HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            log.error(f"[Telegram] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Gmail  (dùng App Password — không cần tắt 2FA)
    # ------------------------------------------------------------------ #
    def _send_gmail(self, message: str):
        if not self.gmail_user or not self.gmail_pass or not self.gmail_to:
            log.warning("[Gmail] GMAIL_USER, GMAIL_APP_PASS hoặc GMAIL_TO chưa cấu hình trong .env.")
            return

        subject  = self._extract_subject(message)
        html_body = self._wrap_html_email(message)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Linux Monitor <{self.gmail_user}>"
        msg["To"]      = self.gmail_to

        msg.attach(MIMEText(message, "plain", "utf-8"))   # fallback plain text
        msg.attach(MIMEText(html_body, "html", "utf-8"))  # HTML đẹp hơn

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(self.gmail_user, self.gmail_pass)
                server.sendmail(self.gmail_user, self.gmail_to.split(","), msg.as_string())
            log.info(f"[Gmail] Gửi cảnh báo thành công đến {self.gmail_to}")
        except smtplib.SMTPAuthenticationError:
            log.error("[Gmail] Sai thông tin xác thực. Hãy kiểm tra GMAIL_USER và GMAIL_APP_PASS.")
        except Exception as e:
            log.error(f"[Gmail] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Office 365
    # ------------------------------------------------------------------ #
    def _send_office365(self, message: str):
        if not self.o365_user or not self.o365_pass or not self.o365_mail_to:
            log.warning("[Office365] O365_USER, O365_PASS hoặc MAIL_TO chưa cấu hình trong .env.")
            return

        subject   = self._extract_subject(message)
        html_body = self._wrap_html_email(message)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self.o365_mail_from
        msg["To"]      = self.o365_mail_to

        msg.attach(MIMEText(message, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP("smtp.office365.com", 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(self.o365_user, self.o365_pass)
                server.sendmail(self.o365_mail_from, self.o365_mail_to.split(","), msg.as_string())
            log.info(f"[Office365] Gửi cảnh báo thành công đến {self.o365_mail_to}")
        except smtplib.SMTPAuthenticationError:
            log.error("[Office365] Sai thông tin xác thực. Kiểm tra O365_USER và O365_PASS / App Password.")
        except Exception as e:
            log.error(f"[Office365] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Viber
    # ------------------------------------------------------------------ #
    def _send_viber(self, message: str):
        if not self.viber_auth_token or not self.viber_receiver_id:
            log.warning("[Viber] VIBER_AUTH_TOKEN hoặc VIBER_RECEIVER_ID chưa cấu hình trong .env.")
            return

        # Strip HTML tags cho Viber (chỉ nhận plain text)
        import re
        plain = re.sub(r"<[^>]+>", "", message)

        url     = "https://chatapi.viber.com/pa/send_message"
        headers = {"X-Viber-Auth-Token": self.viber_auth_token}
        payload = {
            "receiver":        self.viber_receiver_id,
            "min_api_version": 1,
            "sender":          {"name": self.viber_bot_name},
            "tracking_data":   "monitor_alert",
            "type":            "text",
            "text":            plain,
        }
        try:
            resp      = requests.post(url, json=payload, headers=headers, timeout=5)
            resp_data = resp.json()
            if resp_data.get("status") == 0:
                log.info("[Viber] Gửi cảnh báo thành công.")
            else:
                log.error(f"[Viber] Lỗi: {resp_data.get('status_message')}")
        except Exception as e:
            log.error(f"[Viber] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_subject(message: str) -> str:
        """Lấy dòng đầu tiên làm subject email, strip HTML tags"""
        import re
        first_line = message.strip().splitlines()[0] if message.strip() else "Linux Monitor Alert"
        return re.sub(r"<[^>]+>", "", first_line)[:100]

    @staticmethod
    def _wrap_html_email(message: str) -> str:
        """Bọc nội dung HTML trong template email đơn giản"""
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: monospace; background:#1e1e2e; color:#cdd6f4; padding:20px; }}
    .card {{ background:#313244; border-radius:8px; padding:20px; max-width:600px; margin:auto; }}
    pre {{ background:#181825; padding:12px; border-radius:6px; overflow-x:auto; font-size:13px; }}
    code {{ background:#181825; padding:2px 6px; border-radius:4px; }}
    b {{ color:#cba6f7; }}
    i {{ color:#a6e3a1; }}
    hr {{ border-color:#45475a; }}
    .footer {{ color:#585b70; font-size:12px; margin-top:12px; }}
  </style>
</head>
<body>
  <div class="card">
    {message.replace(chr(10), '<br>')}
    <p class="footer">Powered by Linux Monitor System</p>
  </div>
</body>
</html>"""
