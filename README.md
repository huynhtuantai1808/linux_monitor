# 🖥️ Linux Monitor - Hệ thống Giám sát Server

Công cụ giám sát hiệu năng máy chủ Linux theo mô hình **Master - Agent**, viết bằng Python.  
Tự động cảnh báo qua **Telegram**, **Viber**, hoặc **Email Office 365** khi tài nguyên vượt ngưỡng.

---

## 📐 Kiến trúc tổng quan

```
                ┌─────────────────────────────────────┐
                │        MASTER SERVER (Trung tâm)     │
                │                                     │
                │   FastAPI (port 8000)               │
                │      ↓                              │
                │   Alerter (đánh giá ngưỡng)         │
                │      ↓                              │
                │   Notifier ──────────────────────── │──▶ Telegram
                │                                     │──▶ Viber
                │                                     │──▶ Office 365 Email
                └──────────────────┬──────────────────┘
                                   │ HTTP POST /metrics
               ┌───────────────────┼───────────────────┐
               ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Agent - Server1│ │  Agent - Server2│ │  Agent - ServerN│
    │  (psutil)       │ │  (psutil)       │ │  (psutil)       │
    │  monitor.py     │ │  monitor.py     │ │  monitor.py     │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Logic cảnh báo
| Ngưỡng | CPU / RAM / Disk | Load Average |
|--------|-----------------|-------------|
| ✅ OK | < 80% | ≤ 2 |
| ⚠️ WARNING | > 80% | > 2 |
| 🔴 CRITICAL | > 95% | - |

Khi kích hoạt cảnh báo, hệ thống tự động **gửi kèm danh sách top process** đang chiếm tài nguyên nhiều nhất.

---

## 📁 Cấu trúc thư mục

```
linux_monitor/
├── .env.example            # Mẫu cấu hình - xem trước khi setup
├── .gitignore
│
├── master/                 # Đặt trên server trung tâm
│   ├── main.py             # ◀ Lệnh khởi động Master
│   ├── server.py           # API FastAPI nhận metrics
│   ├── alerter.py          # Logic đánh giá ngưỡng Warning/Critical
│   ├── notifier.py         # Gửi cảnh báo (Telegram/Viber/Email)
│   ├── .env                # ◀ Cấu hình kênh alert (KHÔNG commit lên git)
│   └── requirements.txt
│
└── agent/                  # Đặt trên mỗi server cần giám sát
    ├── main.py             # ◀ Lệnh khởi động Agent
    ├── monitor.py          # Thu thập metrics và gửi về Master
    ├── .env                # ◀ Cấu hình MASTER_URL (KHÔNG commit lên git)
    └── requirements.txt
```

---

## 🚀 Hướng dẫn cài đặt

### Yêu cầu hệ thống
- Python 3.8+
- Các server Agent phải có thể kết nối TCP đến IP và Port của Master

---

### ⚙️ 1. Cài đặt Master Server

**Bước 1:** Copy thư mục `master/` lên server trung tâm, sau đó cài thư viện:
```bash
cd linux_monitor/master/
pip install -r requirements.txt
```

**Bước 2:** Tạo file `.env` từ mẫu và điền thông tin:
```bash
cp ../env.example .env
nano .env
```

Nội dung file `.env` (xem chi tiết bên dưới phần **Cấu hình**):
```env
NOTIFY_CHANNEL=telegram
TG_BOT_TOKEN=your_bot_token_here
TG_CHAT_ID=your_chat_id_here
MASTER_HOST=0.0.0.0
MASTER_PORT=8000
```

**Bước 3:** Mở firewall để Agent kết nối vào:
```bash
# UFW
sudo ufw allow 8000/tcp

# Hoặc iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

**Bước 4:** Khởi động Master:
```bash
python main.py
```

Chạy nền với `nohup`:
```bash
nohup python main.py > /var/log/linux-monitor-master.log 2>&1 &
```

---

### 🤖 2. Cài đặt Agent (trên mỗi server cần giám sát)

**Bước 1:** Copy thư mục `agent/` lên server cần giám sát:
```bash
scp -r linux_monitor/agent/ user@<IP_SERVER>:/opt/linux-monitor/
```

**Bước 2:** Cài thư viện:
```bash
cd /opt/linux-monitor/agent/
pip install -r requirements.txt
```

**Bước 3:** Tạo file `.env` và điền IP của Master:
```bash
nano .env
```
```env
# Thay 192.168.1.100 bằng IP thực của Master Server
MASTER_URL=http://192.168.1.100:8000/metrics
INTERVAL=60
```

**Bước 4:** Khởi động Agent:
```bash
python main.py

# Chạy nền
nohup python -r main.py > /var/log/linux-monitor-agent.log 2>&1 &
```

---

## 🔧 Cấu hình chi tiết (file `.env`)

Xem file mẫu đầy đủ tại [`.env.example`](.env.example).

### Telegram
1. Mở Telegram, tìm **@BotFather** → tạo bot mới → lấy `TG_BOT_TOKEN`
2. Gửi 1 tin nhắn cho bot, sau đó truy cập URL sau để lấy `TG_CHAT_ID`:
   ```
   https://api.telegram.org/bot<TG_BOT_TOKEN>/getUpdates
   ```
```env
NOTIFY_CHANNEL=telegram
TG_BOT_TOKEN=123456789:ABCdef...
TG_CHAT_ID=-100123456789
```

### Viber
1. Tạo Viber Public Account tại: https://partners.viber.com
2. Lấy `AUTH_TOKEN` từ dashboard
```env
NOTIFY_CHANNEL=viber
VIBER_AUTH_TOKEN=your_auth_token
VIBER_RECEIVER_ID=your_receiver_id
VIBER_BOT_NAME=Linux Monitor
```

### Office 365 Email
> ⚠️ Nếu tài khoản bật **MFA**, cần tạo **App Password** thay vì dùng mật khẩu thường.  
> Vào: https://mysignins.microsoft.com/security-info → Thêm phương thức → App password
```env
NOTIFY_CHANNEL=office365
O365_USER=alert@company.com
O365_PASS=your_app_password
MAIL_FROM=alert@company.com
MAIL_TO=admin@company.com
```

---

## 💡 Ví dụ tin nhắn cảnh báo

```
[WARNING] Cảnh báo từ Server: web-server-01
RAM usage is HIGH: 87.3%
Load Average is HIGH: 3.2

Các process tốn tài nguyên nhất:
- PID: 1234 | Tên: java    | User: root | CPU: 45.2% | RAM: 62.10%
- PID: 5678 | Tên: mysqld  | User: mysql| CPU: 12.0% | RAM: 18.50%
- PID: 9012 | Tên: nginx   | User: www  | CPU:  2.1% | RAM:  1.20%
```

---

## 🔍 Kiểm tra hoạt động

Sau khi Master đang chạy, kiểm tra API:
```bash
# Health check
curl http://localhost:8000/health

# Gửi thủ công metric test (giả lập CPU cao)
curl -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "test-server",
    "cpu_percent": 97,
    "ram_percent": 45,
    "disk_percent": 30,
    "load_avg_1": 1.5,
    "load_avg_5": 1.2,
    "load_avg_15": 1.0,
    "top_processes": [
      {"pid": 1234, "name": "stress", "username": "root", "cpu_percent": 96.0, "memory_percent": 5.0}
    ]
  }'
```
