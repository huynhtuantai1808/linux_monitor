#!/usr/bin/env python3
"""
Linux Monitor - Windows Agent
Entry point: python main.py
Configure via the .env file in the same directory

Requirement: Set MASTER_URL in .env to point to the Master Server IP
"""
import os
import sys
from dotenv import load_dotenv

# Load .env before importing other modules
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from monitor import main

if __name__ == "__main__":
    master_url = os.environ.get("MASTER_URL", "http://127.0.0.1:8000/metrics")
    interval   = os.environ.get("INTERVAL", "60")
    drives     = os.environ.get("MONITOR_DRIVES", "All available drives")

    print("=" * 60)
    print("  Linux Monitor - Windows Agent")
    print("=" * 60)
    print(f"  Master URL       : {master_url}")
    print(f"  Check interval   : every {interval} seconds")
    print(f"  Monitored drives : {drives}")
    print("=" * 60)

    main()
