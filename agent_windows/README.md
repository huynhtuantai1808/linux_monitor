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
## 🚀 Installation Guide

### Requirements
- Python 3.8+
- Agent servers must be able to reach the Master via TCP on the configured port

---

### 🪟 1. Windows Agent Setup

**Step 1:** Copy `agent_windows/` to the Windows server, install Python 3.8+ if needed.

**Step 2:** Install dependencies (run in Command Prompt or PowerShell):
```bat
cd agent_windows
python -m venv venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
venv\Scripts\activate
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

# Optional: monitor specific drives only (leave blank for all)
# MONITOR_DRIVES=C:,D:
```

**Step 4:** Start the Agent:
```bat
python main.py

:: Run silently in background via PowerShell
Start-Process python -ArgumentList "-u main.py" -WindowStyle Hidden -RedirectStandardOutput "C:\Logs\monitor-agent.log" -RedirectStandardError "C:\Logs\monitor-agent-err.log"
```
**Step 5:** Stop the Agent:
```bat
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId, CommandLine
Stop-Process -Id xxxxx -Force
```

> **Key differences — Windows vs Linux Agent:**
>
> | Feature | Linux | Windows |
> |---------|-------|---------|
> | Load Average | `os.getloadavg()` | Rolling CPU% average (15 samples) |
> | Disk | Root partition `/` | All drives `C:\`, `D:\`, ... |
> | OS Label in alert | 🐧 Linux | 🪟 Windows |
> | Extra payload | — | `disks[]` per-drive detail |


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
