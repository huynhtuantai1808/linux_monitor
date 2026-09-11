# 🖥️ Linux Monitor - Server Performance Monitoring System

A **Master-Agent** architecture monitoring tool written in Python.  
Automatically alerts via **Telegram**, **Gmail**, **Viber**, or **Office 365** when system resources exceed thresholds.  
Supports both **Linux** 🐧 and **Windows** 🪟 agents reporting to a single Master.

---

## 📐 Architecture Overview

```
                ┌──────────────────────────────────────────────┐
                │             MASTER SERVER (Central)           │
                │                                              │
                │   FastAPI (port 8000)                        │
                │      ↓                                       │
                │   Alerter  (evaluate WARNING / CRITICAL)     │
                │      ↓                                       │
                │   Notifier (multi-channel dispatch) ──────── │──▶ Telegram
                │                                              │──▶ Gmail
                │                                              │──▶ Viber
                │                                              │──▶ Office 365
                └────────────────┬─────────────────────────────┘
                                 │ HTTP POST /metrics
          ┌──────────────────────┼────────────────────────┐
          ▼                      ▼                        ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  🐧 Linux Agent  │  │  🐧 Linux Agent  │  │  🪟 Windows Agent│
│  agent/          │  │  agent/          │  │  agent_windows/  │
│  monitor.py      │  │  monitor.py      │  │  monitor.py      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Alert Thresholds

| Level | CPU / RAM / Disk | Load Avg (Linux) / CPU Avg (Windows) |
|-------|-----------------|--------------------------------------|
| ✅ OK | < 80% | ≤ 2 |
| ⚠️ WARNING | > 80% | > 2 |
| 🔴 CRITICAL | > 95% | — |

When an alert is triggered, the system automatically **attaches the top resource-consuming processes**.

---

## 📁 Project Structure

```
linux_monitor/
├── .env.example            # Config template — read before setup
├── .gitignore              # Prevents .env files from being committed
│
├── master/                 # Deploy on the central server
│   ├── main.py             # ◀ Entry point — start with: python main.py
│   ├── server.py           # FastAPI server receiving metrics
│   ├── alerter.py          # Threshold evaluation (Warning/Critical)
│   ├── notifier.py         # Multi-channel alert dispatcher
│   ├── .env                # ◀ Alert channel config (DO NOT commit)
│   └── requirements.txt
│
├── agent/                  # Deploy on each Linux server to monitor
│   ├── main.py             # ◀ Entry point — start with: python main.py
│   ├── monitor.py          # Collects metrics and pushes to Master
│   ├── .env                # ◀ Set MASTER_URL here (DO NOT commit)
│   └── requirements.txt
│
└── agent_windows/          # Deploy on each Windows server to monitor
    ├── main.py             # ◀ Entry point — start with: python main.py
    ├── monitor.py          # Windows-specific metrics + all drives
    ├── .env                # ◀ Set MASTER_URL here (DO NOT commit)
    └── requirements.txt
```

---

## 🚀 Installation Guide

### Requirements
- Python 3.8+
- Agent servers must be able to reach the Master via TCP on the configured port

---

### ⚙️ 1. Master Server Setup

**Step 1:** Copy `master/` to your central server, then install dependencies:
```bash
cd linux_monitor/master/
pip install -r requirements.txt
```

**Step 2:** Create `.env` from the template and fill in your config:
```bash
cp ../.env.example master/.env
nano master/.env
```

Minimal `.env` content (see **Configuration** section below for all options):
```env
# Comma-separated: telegram | gmail | office365 | viber
NOTIFY_CHANNELS=telegram,gmail

TG_BOT_TOKEN=your_bot_token_here
TG_CHAT_ID=your_chat_id_here

MASTER_HOST=0.0.0.0
MASTER_PORT=8000
```

**Step 3:** Open firewall for Agents to connect:
```bash
# UFW
sudo ufw allow 8000/tcp

# Or iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

**Step 4:** Start the Master:
```bash
python main.py

# Run in background (note: use -u for real-time log flushing)
nohup python -u main.py > /var/log/linux-monitor-master.log 2>&1 &
tail -f /var/log/linux-monitor-master.log
```

---

> **Key differences — Windows vs Linux Agent:**
>
> | Feature | Linux | Windows |
> |---------|-------|---------|
> | Load Average | `os.getloadavg()` | Rolling CPU% average (15 samples) |
> | Disk | Root partition `/` | All drives `C:\`, `D:\`, ... |
> | OS Label in alert | 🐧 Linux | 🪟 Windows |
> | Extra payload | — | `disks[]` per-drive detail |

---

## 🔧 Configuration Details (`master/.env`)

See the full template at [`.env.example`](.env.example).

### NOTIFY_CHANNELS (multi-channel)

```env
# Send to ONE channel
NOTIFY_CHANNELS=telegram

# Send to MULTIPLE channels simultaneously
NOTIFY_CHANNELS=telegram,gmail

# Send to ALL channels
NOTIFY_CHANNELS=telegram,gmail,office365,viber
```

| Value | Behaviour |
|-------|-----------|
| `telegram` | Sends to Telegram only |
| `gmail` | Sends to Gmail only |
| `telegram,gmail` | Sends to both at the same time |
| `telegram,gmail,office365,viber` | Sends to all 4 channels |

---

### 📱 Telegram
1. Find **@BotFather** on Telegram → create a new bot → copy the Bot Token
2. Send a message to the bot, then open this URL to get the `chat_id`:
   ```
   https://api.telegram.org/bot<TG_BOT_TOKEN>/getUpdates
   ```
```env
TG_BOT_TOKEN=123456789:ABCdef...
TG_CHAT_ID=-100123456789
```

---

### 📧 Gmail
> ⚠️ **Do NOT use your regular Gmail password.** You must create an **App Password** (16 characters).
> 1. Enable 2-Step Verification on your Google account
> 2. Go to: https://myaccount.google.com/apppasswords
> 3. Select **Mail → Other (e.g. "Linux Monitor")** → Copy the 16-char password

```env
GMAIL_USER=your_gmail@gmail.com
GMAIL_APP_PASS=xxxx xxxx xxxx xxxx
GMAIL_TO=admin@gmail.com,ops@company.com
```

---

### 💼 Office 365 Email
> ⚠️ If MFA is enabled, create an **App Password** at:  
> https://mysignins.microsoft.com/security-info → Add method → App password

```env
O365_USER=alert@company.com
O365_PASS=your_app_password
MAIL_FROM=alert@company.com
MAIL_TO=admin@company.com
```

---

### 📲 Viber
1. Create a Viber Bot at: https://partners.viber.com
2. Copy `AUTH_TOKEN` from the dashboard

```env
VIBER_AUTH_TOKEN=your_auth_token
VIBER_RECEIVER_ID=your_receiver_id
VIBER_BOT_NAME=Linux Monitor
```

---

## 💡 Sample Alert Message (Telegram)

**Linux agent alert:**
```
⚠️ [WARNING] web-server-01  🐧 Linux
🕐 2026-09-11 08:59:00

📊 Resource thresholds exceeded:
  • ⚠️ RAM:  87.3%  (Warning > 80%)
  • 📈 Load Avg: 3.20  (High > 2.0)

⚙️ Top resource-consuming processes:
PID      Name               CPU%   RAM%  User
──────── ────────────────── ────── ──────────
1234     java               45.2%  62.10%  root
5678     mysqld             12.0%  18.50%  mysql
─────────────────────────
🤖 Linux Monitor System
```

**Windows agent alert:**
```
🔴 [CRITICAL] WIN-SERVER-01  🪟 Windows
🕐 2026-09-11 08:59:00

📊 Resource thresholds exceeded:
  • 🔴 CPU:  96.5%  (Critical > 95%)
  • ⚠️ Disk: 85.3%  (Warning > 80%)

💾 Disk Usage per Drive:
Drive    Used    Total    Free      %
C:\   120.5GB  200.0GB  79.5GB  60.2%
D:\   450.0GB  500.0GB  50.0GB  90.1% ⚠️

⚙️ Top resource-consuming processes:
PID      Name               CPU%   RAM%  User
──────── ────────────────── ────── ──────────
4512     java               95.1%  22.50%  SYSTEM
─────────────────────────
🤖 Linux Monitor System
```

---

## 🔍 Verify the System is Working

After starting the Master, test the API:
```bash
# Health check
curl http://localhost:8000/health

# Simulate a Linux agent sending CRITICAL CPU metrics
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "test-linux-server",
    "os": "linux",
    "cpu_percent": 97,
    "ram_percent": 88,
    "disk_percent": 30,
    "load_avg_1": 3.5,
    "load_avg_5": 2.8,
    "load_avg_15": 2.1,
    "top_processes": [
      {"pid": 1234, "name": "stress", "username": "root", "cpu_percent": 96.0, "memory_percent": 5.0}
    ]
  }'

# Simulate a Windows agent with multi-drive disk data
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "WIN-SERVER-01",
    "os": "windows",
    "cpu_percent": 45,
    "ram_percent": 60,
    "disk_percent": 91,
    "load_avg_1": 1.0,
    "load_avg_5": 1.0,
    "load_avg_15": 1.0,
    "disks": [
      {"mount": "C:\\\\", "total_gb": 200, "used_gb": 120, "free_gb": 80, "percent": 60},
      {"mount": "D:\\\\", "total_gb": 500, "used_gb": 455, "free_gb": 45, "percent": 91}
    ],
    "top_processes": []
  }'
```

---

## 📋 Changelog

| Version | Change |
|---------|--------|
| v1.3 | Added **Windows Agent** (`agent_windows/`) with per-drive disk monitoring and CPU rolling average |
| v1.2 | **Multi-channel** support via `NOTIFY_CHANNELS` (comma-separated: telegram, gmail, office365, viber) |
| v1.2 | Added **Gmail** SMTP with App Password support |
| v1.1 | Alert messages reformatted to **HTML** for rich Telegram rendering |
| v1.1 | Switched to Python `logging` module with `-u` flag for **real-time nohup logging** |
| v1.0 | Initial release — Linux Master-Agent with Telegram / Viber / Office 365 |
