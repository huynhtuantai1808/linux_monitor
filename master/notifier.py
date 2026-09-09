import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load biến môi trường từ file .env cùng thư mục
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


class Notifier:
    def __init__(self):
        self.channel = os.environ.get("NOTIFY_CHANNEL", "telegram").lower()

        # --- Telegram ---
        self.tg_bot_token = os.environ.get("TG_BOT_TOKEN", "")
        self.tg_chat_id = os.environ.get("TG_CHAT_ID", "")

        # --- Viber ---
        self.viber_auth_token = os.environ.get("VIBER_AUTH_TOKEN", "")
        self.viber_receiver_id = os.environ.get("VIBER_RECEIVER_ID", "")
        self.viber_bot_name = os.environ.get("VIBER_BOT_NAME", "Linux Monitor")

        # --- Office 365 / SMTP ---
        self.smtp_server = "smtp.office365.com"
        self.smtp_port = 587
        self.smtp_user = os.environ.get("O365_USER", "")
        self.smtp_pass = os.environ.get("O365_PASS", "")
        self.mail_to = os.environ.get("MAIL_TO", "")
        self.mail_from = os.environ.get("MAIL_FROM", self.smtp_user)

    def send_alert(self, message: str):
        """Gửi cảnh báo qua kênh được cấu hình trong .env"""
        if self.channel == "telegram":
            self._send_telegram(message)
        elif self.channel in ("email", "office365"):
            self._send_email(message)
        elif self.channel == "viber":
            self._send_viber(message)
        else:
            print(f"[Console Notifier - Kênh không xác định: {self.channel}]\n{message}")

    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    def _send_telegram(self, message: str):
        if not self.tg_bot_token or not self.tg_chat_id:
            print("[Telegram] Token hoặc Chat ID chưa cấu hình trong .env. In ra Console:")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return

        url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
        payload = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                print("[Telegram] Gửi cảnh báo thành công.")
            else:
                print(f"[Telegram] Lỗi HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[Telegram] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Viber
    # ------------------------------------------------------------------ #
    def _send_viber(self, message: str):
        if not self.viber_auth_token or not self.viber_receiver_id:
            print("[Viber] AUTH_TOKEN hoặc RECEIVER_ID chưa cấu hình trong .env. In ra Console:")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return

        url = "https://chatapi.viber.com/pa/send_message"
        headers = {"X-Viber-Auth-Token": self.viber_auth_token}
        payload = {
            "receiver": self.viber_receiver_id,
            "min_api_version": 1,
            "sender": {"name": self.viber_bot_name},
            "tracking_data": "monitor_alert",
            "type": "text",
            "text": message,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            resp_data = resp.json()
            if resp_data.get("status") == 0:
                print("[Viber] Gửi cảnh báo thành công.")
            else:
                print(f"[Viber] Lỗi: {resp_data.get('status_message')}")
        except Exception as e:
            print(f"[Viber] Ngoại lệ: {e}")

    # ------------------------------------------------------------------ #
    # Office 365 Email
    # ------------------------------------------------------------------ #
    def _send_email(self, message: str):
        if not self.smtp_user or not self.smtp_pass or not self.mail_to:
            print("[Email] Thông tin SMTP chưa cấu hình trong .env. In ra Console:")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return

        subject = "[LINUX MONITOR] Cảnh báo hệ thống"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.mail_from
        msg["To"] = self.mail_to
        msg.attach(MIMEText(message, "plain", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.mail_from, self.mail_to.split(","), msg.as_string())
            print(f"[Email] Gửi cảnh báo thành công đến {self.mail_to}")
        except Exception as e:
            print(f"[Email] Ngoại lệ: {e}")
