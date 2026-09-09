#!/usr/bin/env python3
"""
Linux Monitor - Agent
Entry point: python main.py
Cấu hình tại file .env trong cùng thư mục

Yêu cầu: Điền MASTER_URL vào file .env trỏ đến IP của Master Server
"""
import os
from dotenv import load_dotenv

# Load .env trước khi import module khác
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from monitor import main

if __name__ == "__main__":
    master_url = os.environ.get("MASTER_URL", "http://127.0.0.1:8000/metrics")
    interval = os.environ.get("INTERVAL", "60")

    print("=" * 60)
    print("  Linux Monitor - Agent")
    print("=" * 60)
    print(f"  Master URL    : {master_url}")
    print(f"  Chu kỳ kiểm tra: mỗi {interval} giây")
    print("=" * 60)

    main()
