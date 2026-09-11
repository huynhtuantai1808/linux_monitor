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

## 📊 Metrics Collected

### Both Agents (Linux & Windows)

| Metric | Description |
|--------|-------------|
| `hostname` | Server hostname |
| `ip_address` | Primary outbound IP (5-stage fallback detection) |
| `cpu_percent` | CPU usage % |
| `cpu_count` | Number of logical CPU cores |
| `ram_percent` | RAM usage % |
| `ram_total_gb` / `ram_used_gb` | Absolute RAM values |
| `swap_percent` / `swap_used_gb` | Swap (Linux) or Pagefile (Windows) |
| `disk_percent` | Highest disk usage % |
| `disk_io` | Disk read/write speed in MB/s |
| `load_avg_1/5/15` | Load Average (Linux) / Rolling CPU avg (Windows) |
| `top_processes` | Top processes with CPU%, RAM%, and **absolute RAM (MB/GB)** |

### Windows Agent Only

| Metric | Description |
|--------|-------------|
| `disks[]` | Per-drive detail: mount, used_gb, total_gb, free_gb, percent |

### IP Address Detection — 5-Stage Fallback

The agent automatically detects the correct primary NIC using a progressive fallback chain:

```
Stage 1 → UDP probe to 8.8.8.8        : internet-facing servers
Stage 2 → UDP probe to Master IP       : local servers that can reach Master
Stage 3 → UDP probe to gateway IPs     : isolated LAN (tries 10.0.0.1, 192.168.x.1...)
Stage 4 → psutil interface scan        : skips loopback & APIPA (169.254.x.x)
Stage 5 → socket.gethostbyname()       : final hostname DNS resolution
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

# Run in background (use -u for real-time log flushing)
nohup python -u main.py > /var/log/linux-monitor-master.log 2>&1 &
tail -f /var/log/linux-monitor-master.log
```

---

### 🐧 2. Linux Agent Setup

**Step 1:** Copy `agent/` to the server you want to monitor:
```bash
scp -r linux_monitor/agent/ user@<SERVER_IP>:/opt/linux-monitor/
```

**Step 2:** Install dependencies:
```bash
cd /opt/linux-monitor/agent/
pip install -r requirements.txt
```

**Step 3:** Create `.env` and point to your Master:
```bash
nano .env
```
```env
# Replace with your Master Server's actual IP
MASTER_URL=http://192.168.1.100:8000/metrics
INTERVAL=60
```

**Step 4:** Start the Agent:
```bash
python main.py

# Run in background with real-time logging
nohup python -u main.py > /var/log/linux-monitor-agent.log 2>&1 &
tail -f /var/log/linux-monitor-agent.log
```

---

### 🪟 3. Windows Agent Setup

**Step 1:** Copy `agent_windows/` to the Windows server, install Python 3.8+ if needed.

**Step 2:** Install dependencies (run in Command Prompt or PowerShell):
```bat
cd agent_windows
pip install -r requirements.txt
```

**Step 3:** Edit `.env`:
```bat
notepad .env
```
```env
# Replace with your Master Server IP
MASTER_URL=http://192.168.1.100:8000/metrics
INTERVAL=60

# Optional: monitor specific drives only (leave blank for all drives)
# Accepts: C:, D:, E: or C, D, E (colon is optional)
# MONITOR_DRIVES=C:,E:
```

**Step 4:** Start the Agent:
```bat
python main.py

:: Run silently in background via PowerShell
Start-Process python -ArgumentList "-u main.py" -WindowStyle Hidden -RedirectStandardOutput "C:\Logs\monitor-agent.log" -RedirectStandardError "C:\Logs\monitor-agent-err.log"
```

**Step 5:** Stop the Agent (PowerShell):
```bat
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId, CommandLine
Stop-Process -Id <PID> -Force
```

> **Key differences — Windows vs Linux Agent:**
>
> | Feature | Linux | Windows |
> |---------|-------|---------|
> | Load Average | `os.getloadavg()` | Rolling CPU% average (15 samples) |
> | Disk | Root partition `/` | All drives `C:\`, `D:\`, ... |
> | Swap metric | Swap usage | Pagefile usage |
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



---

## 🔍 Verify the System is Working

After starting the Master, test the API:
```bash
# Health check
curl http://localhost:8000/health

# Simulate a Linux agent sending CRITICAL RAM + high load
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "test-linux-server",
    "ip_address": "10.0.0.5",
    "os": "linux",
    "cpu_percent": 45,
    "cpu_count": 4,
    "ram_percent": 97,
    "ram_total_gb": 32.0,
    "ram_used_gb": 31.0,
    "swap_percent": 76.2,
    "swap_total_gb": 8.0,
    "swap_used_gb": 6.1,
    "disk_percent": 30,
    "load_avg_1": 5.6,
    "load_avg_5": 4.2,
    "load_avg_15": 3.1,
    "disk_io": {"read_mbps": 124.5, "write_mbps": 38.2},
    "top_processes": [
      {"pid": 1234, "name": "java", "username": "root", "cpu_percent": 45.0, "memory_percent": 12.5, "ram_mb": 4096}
    ]
  }'

# Simulate a Windows agent with per-drive disk data
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "WIN-SERVER-01",
    "ip_address": "10.10.20.214",
    "os": "windows",
    "cpu_percent": 45,
    "cpu_count": 14,
    "ram_percent": 93,
    "ram_total_gb": 15.6,
    "ram_used_gb": 14.5,
    "swap_percent": 15.1,
    "swap_total_gb": 20.0,
    "swap_used_gb": 3.0,
    "disk_percent": 68,
    "load_avg_1": 11.3,
    "load_avg_5": 9.5,
    "load_avg_15": 8.2,
    "disk_io": {"read_mbps": 0.0, "write_mbps": 0.0},
    "disks": [
      {"mount": "C:\\\\", "total_gb": 209.9, "used_gb": 144.3, "free_gb": 65.6, "percent": 68.8},
      {"mount": "E:\\\\", "total_gb": 266.2, "used_gb": 122.5, "free_gb": 143.7, "percent": 46.0}
    ],
    "top_processes": [
      {"pid": 33580, "name": "vmmemWSL", "username": "NT VIRTUAL MACHINE", "cpu_percent": 0.0, "memory_percent": 6.8, "ram_mb": 1024}
    ]
  }'
```

---

## 📋 Changelog

| Version | Change |
|---------|--------|
| v1.5 | **5-stage IP fallback** — detects primary NIC on both internet and isolated local servers |
| v1.5 | **Swap/Pagefile alert** — warns when swap > 70% while RAM is also high (OOM risk) |
| v1.5 | **Disk I/O** — real-time read/write MB/s delta per check interval |
| v1.5 | **RAM absolute values** — alert shows `96.3% of 32.0GB` instead of just `96.3%` |
| v1.5 | **Load Avg with cores** — shows `5.60 / 4 cores` for accurate context |
| v1.5 | **Process RAM in MB/GB** — absolute memory per process in the top process table |
| v1.4 | **IP Address** in alert header — `🌐 103.72.98.212` for quick server identification |
| v1.3 | Added **Windows Agent** (`agent_windows/`) with per-drive disk monitoring and CPU rolling average |
| v1.2 | **Multi-channel** support via `NOTIFY_CHANNELS` (comma-separated: telegram, gmail, office365, viber) |
| v1.2 | Added **Gmail** SMTP with App Password support |
| v1.1 | Alert messages reformatted to **HTML** for rich Telegram rendering |
| v1.1 | Switched to Python `logging` module with `-u` flag for **real-time nohup logging** |
| v1.0 | Initial release — Linux Master-Agent with Telegram / Viber / Office 365 |
