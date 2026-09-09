import datetime
from notifier import Notifier

# Kênh cảnh báo được đọc tự động từ file .env (NOTIFY_CHANNEL)
notifier = Notifier()


def _get_level_icon(level: str) -> str:
    return {"CRITICAL": "🔴", "WARNING": "⚠️"}.get(level, "✅")


def _get_metric_icon(name: str, level: str) -> str:
    icons = {"cpu": "🖥️", "ram": "🧠", "disk": "💾", "load": "📈"}
    badge = "🔴" if level == "CRITICAL" else "⚠️"
    return f"{badge} {icons.get(name, '📌')}"


def format_process_table(processes: list) -> str:
    if not processes:
        return "_Không có thông tin tiến trình._"

    lines = [
        "```",
        f"{'PID':<8} {'Name':<16} {'CPU%':>6} {'RAM%':>6} {'User'}",
        f"{'-'*8} {'-'*16} {'-'*6} {'-'*6} {'-'*10}",
    ]
    for p in processes:
        pid  = str(p.get("pid", "-"))
        name = (p.get("name") or "-")[:16]
        cpu  = f"{p.get('cpu_percent', 0):.1f}"
        ram  = f"{p.get('memory_percent', 0):.1f}"
        user = (p.get("username") or "-")[:12]
        lines.append(f"{pid:<8} {name:<16} {cpu:>6} {ram:>6} {user}")
    lines.append("```")
    return "\n".join(lines)


def build_markdown_message(level: str, hostname: str, alerts: list, processes: list) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon = _get_level_icon(level)

    lines = [
        f"{icon} *\\[{level}\\] {hostname}*",
        f"🕐 `{now}`",
        "",
        "📊 *Thông số vượt ngưỡng:*",
    ]

    for alert in alerts:
        lines.append(f"  • {alert}")

    if processes:
        lines.append("")
        lines.append("⚙️ *Top Processes chiếm tài nguyên:*")
        lines.append(format_process_table(processes))

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("🤖 _Linux Monitor System_")

    return "\n".join(lines)


def evaluate_metrics(metrics: dict):
    hostname = metrics.get("hostname", "Unknown")
    cpu      = metrics.get("cpu_percent", 0)
    ram      = metrics.get("ram_percent", 0)
    disk     = metrics.get("disk_percent", 0)
    load     = metrics.get("load_avg_1", 0)
    processes = metrics.get("top_processes", [])

    alerts = []
    level  = "OK"

    # ── Critical (> 95%) ──────────────────────────────────────
    if cpu > 95 or ram > 95 or disk > 95:
        level = "CRITICAL"
        if cpu  > 95: alerts.append(f"🔴 CPU:  `{cpu}%`  _(Critical \\> 95%)_")
        if ram  > 95: alerts.append(f"🔴 RAM:  `{ram}%`  _(Critical \\> 95%)_")
        if disk > 95: alerts.append(f"🔴 Disk: `{disk}%` _(Critical \\> 95%)_")

    # ── Warning (> 80%) ───────────────────────────────────────
    elif cpu > 80 or ram > 80 or disk > 80:
        level = "WARNING"
        if cpu  > 80: alerts.append(f"⚠️ CPU:  `{cpu}%`  _(Warning \\> 80%)_")
        if ram  > 80: alerts.append(f"⚠️ RAM:  `{ram}%`  _(Warning \\> 80%)_")
        if disk > 80: alerts.append(f"⚠️ Disk: `{disk}%` _(Warning \\> 80%)_")

    # ── Load Average ──────────────────────────────────────────
    if load > 2:
        if level == "OK":
            level = "WARNING"
        alerts.append(f"📈 Load Average: `{load:.2f}` _(High \\> 2\\.0)_")

    if alerts:
        message = build_markdown_message(level, hostname, alerts, processes)
        print(f"Đang gửi cảnh báo {level} cho {hostname}...")
        notifier.send_alert(message)
    else:
        print(f"[{hostname}] Metrics OK — CPU: {cpu}% | RAM: {ram}% | Disk: {disk}% | Load: {load:.2f}")
