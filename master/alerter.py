import datetime
from notifier import Notifier

# Notification channel is auto-loaded from .env (NOTIFY_CHANNELS)
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


def build_message(
    level: str,
    hostname: str,
    alerts: list,
    processes: list,
    os_name: str = "linux",
    disks: list = None,
) -> str:
    """Build an HTML-formatted alert message for Telegram."""
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon = "🔴" if level == "CRITICAL" else "⚠️"
    os_badge = "🪟 Windows" if os_name == "windows" else "🐧 Linux"

    lines = [
        f"{icon} <b>[{level}] {hostname}</b>  <i>{os_badge}</i>",
        f"🕐 <code>{now}</code>",
        "",
        "📊 <b>Resource thresholds exceeded:</b>",
    ]

    for alert in alerts:
        lines.append(f"  • {alert}")

    # Show per-drive disk detail for Windows agents
    if os_name == "windows" and disks:
        lines.append("")
        lines.append("💾 <b>Disk Usage per Drive:</b>")
        drive_rows = [f"{'Drive':<8} {'Used':>8} {'Total':>8} {'Free':>8} {'%':>6}"]
        drive_rows.append("-" * 44)
        for d in disks:
            flag = " ⚠️" if d["percent"] > 80 else ""
            drive_rows.append(
                f"{d['mount']:<8} {d['used_gb']:>6.1f}GB {d['total_gb']:>6.1f}GB "
                f"{d['free_gb']:>6.1f}GB {d['percent']:>5.1f}%{flag}"
            )
        nl = "\n"
        lines.append(f"<pre>{nl.join(drive_rows)}</pre>")

    if processes:
        lines.append("")
        lines.append("⚙️ <b>Top resource-consuming processes:</b>")
        lines.append(f"<pre>{format_process_table(processes)}</pre>")

    lines.append("─" * 25)
    lines.append("🤖 <i>Linux Monitor System</i>")

    return "\n".join(lines)


def evaluate_metrics(metrics: dict):
    hostname  = metrics.get("hostname", "Unknown")
    os_name   = metrics.get("os", "linux").lower()          # "windows" or "linux"
    cpu       = metrics.get("cpu_percent", 0)
    ram       = metrics.get("ram_percent", 0)
    disk      = metrics.get("disk_percent", 0)
    load      = metrics.get("load_avg_1", 0)
    processes = metrics.get("top_processes", [])
    disks     = metrics.get("disks", [])                     # Windows per-drive list

    alerts = []
    level  = "OK"

    # ── Critical (> 95%) ──────────────────────────────
    if cpu > 95 or ram > 95 or disk > 95:
        level = "CRITICAL"
        if cpu  > 95: alerts.append(f"🔴 CPU:  <code>{cpu}%</code>  <i>(Critical &gt; 95%)</i>")
        if ram  > 95: alerts.append(f"🔴 RAM:  <code>{ram}%</code>  <i>(Critical &gt; 95%)</i>")
        if disk > 95: alerts.append(f"🔴 Disk: <code>{disk}%</code> <i>(Critical &gt; 95%)</i>")

    # ── Warning (> 80%) ──────────────────────────────
    elif cpu > 80 or ram > 80 or disk > 80:
        level = "WARNING"
        if cpu  > 80: alerts.append(f"⚠️ CPU:  <code>{cpu}%</code>  <i>(Warning &gt; 80%)</i>")
        if ram  > 80: alerts.append(f"⚠️ RAM:  <code>{ram}%</code>  <i>(Warning &gt; 80%)</i>")
        if disk > 80: alerts.append(f"⚠️ Disk: <code>{disk}%</code> <i>(Warning &gt; 80%)</i>")

    # ── Load Average (Linux) / CPU Rolling Avg (Windows) ───────
    if load > 2:
        if level == "OK":
            level = "WARNING"
        label = "CPU Avg" if os_name == "windows" else "Load Avg"
        alerts.append(f"📈 {label}: <code>{load:.2f}</code> <i>(High &gt; 2.0)</i>")

    if alerts:
        message = build_message(level, hostname, alerts, processes, os_name, disks)
        print(f"Sending {level} alert for {hostname} [{os_name}]...", flush=True)
        notifier.send_alert(message)
    else:
        print(
            f"[{hostname}] OK — CPU:{cpu}% RAM:{ram}% Disk:{disk}% "
            f"{'CPUAvg' if os_name == 'windows' else 'Load'}:{load:.2f}",
            flush=True
        )
