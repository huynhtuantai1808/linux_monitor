import datetime
from notifier import Notifier

# Kênh cảnh báo được đọc tự động từ file .env (NOTIFY_CHANNEL)
notifier = Notifier()


def format_process_table(processes: list) -> str:
    if not processes:
        return ""
    lines = [
        f"{'PID':<8} {'Name':<18} {'CPU%':>6} {'RAM%':>6}  User",
        f"{'─'*8} {'─'*18} {'─'*6} {'─'*6}  {'─'*10}",
    ]
    for p in processes:
        pid  = str(p.get("pid", "-"))
        name = (p.get("name") or "-")[:18]
        cpu  = f"{p.get('cpu_percent', 0):.1f}%"
        ram  = f"{p.get('memory_percent', 0):.2f}%"
        user = (p.get("username") or "-")[:12]
        lines.append(f"{pid:<8} {name:<18} {cpu:>6} {ram:>6}  {user}")
    return "\n".join(lines)


def build_message(level: str, hostname: str, alerts: list, processes: list) -> str:
    """Tạo tin nhắn định dạng HTML cho Telegram"""
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon = "🔴" if level == "CRITICAL" else "⚠️"

    lines = [
        f"{icon} <b>[{level}] {hostname}</b>",
        f"🕐 <code>{now}</code>",
        "",
        "📊 <b>Thông số vượt ngưỡng:</b>",
    ]

    for alert in alerts:
        lines.append(f"  • {alert}")

    if processes:
        lines.append("")
        lines.append("⚙️ <b>Top Processes chiếm tài nguyên:</b>")
        lines.append(f"<pre>{format_process_table(processes)}</pre>")

    lines.append("─────────────────────────")
    lines.append("🤖 <i>Linux Monitor System</i>")

    return "\n".join(lines)


def evaluate_metrics(metrics: dict):
    hostname  = metrics.get("hostname", "Unknown")
    cpu       = metrics.get("cpu_percent", 0)
    ram       = metrics.get("ram_percent", 0)
    disk      = metrics.get("disk_percent", 0)
    load      = metrics.get("load_avg_1", 0)
    processes = metrics.get("top_processes", [])

    alerts = []
    level  = "OK"

    # ── Critical (> 95%) ──────────────────────────────────────
    if cpu > 95 or ram > 95 or disk > 95:
        level = "CRITICAL"
        if cpu  > 95: alerts.append(f"🔴 CPU:  <code>{cpu}%</code>  <i>(Critical &gt; 95%)</i>")
        if ram  > 95: alerts.append(f"🔴 RAM:  <code>{ram}%</code>  <i>(Critical &gt; 95%)</i>")
        if disk > 95: alerts.append(f"🔴 Disk: <code>{disk}%</code> <i>(Critical &gt; 95%)</i>")

    # ── Warning (> 80%) ───────────────────────────────────────
    elif cpu > 80 or ram > 80 or disk > 80:
        level = "WARNING"
        if cpu  > 80: alerts.append(f"⚠️ CPU:  <code>{cpu}%</code>  <i>(Warning &gt; 80%)</i>")
        if ram  > 80: alerts.append(f"⚠️ RAM:  <code>{ram}%</code>  <i>(Warning &gt; 80%)</i>")
        if disk > 80: alerts.append(f"⚠️ Disk: <code>{disk}%</code> <i>(Warning &gt; 80%)</i>")

    # ── Load Average ──────────────────────────────────────────
    if load > 2:
        if level == "OK":
            level = "WARNING"
        alerts.append(f"📈 Load Avg: <code>{load:.2f}</code> <i>(High &gt; 2.0)</i>")

    if alerts:
        message = build_message(level, hostname, alerts, processes)
        print(f"Đang gửi cảnh báo {level} cho {hostname}...", flush=True)
        notifier.send_alert(message)
    else:
        print(f"[{hostname}] OK — CPU:{cpu}% RAM:{ram}% Disk:{disk}% Load:{load:.2f}", flush=True)
