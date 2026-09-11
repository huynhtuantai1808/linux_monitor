import datetime
from notifier import Notifier

# Notification channel is auto-loaded from .env (NOTIFY_CHANNELS)
notifier = Notifier()


def _fmt_mb(mb: float) -> str:
    """Format MB value to human-readable string (MB or GB)."""
    if mb >= 1024:
        return f"{mb / 1024:.1f}GB"
    return f"{mb:.0f}MB"


def format_process_table(processes: list) -> str:
    """Render top process list as a fixed-width text table."""
    if not processes:
        return ""
    lines = [
        f"{'PID':<8} {'Name':<18} {'CPU%':>6} {'RAM%':>6} {'RAM':>8}  User",
        f"{'─'*8} {'─'*18} {'─'*6} {'─'*6} {'─'*8}  {'─'*10}",
    ]
    for p in processes:
        pid  = str(p.get("pid", "-"))
        name = (p.get("name") or "-")[:18]
        cpu  = f"{p.get('cpu_percent', 0):.1f}%"
        ram  = f"{p.get('memory_percent', 0):.1f}%"
        rabs = _fmt_mb(p.get("ram_mb", 0))
        user = (p.get("username") or "-")[:12]
        lines.append(f"{pid:<8} {name:<18} {cpu:>6} {ram:>6} {rabs:>8}  {user}")
    return "\n".join(lines)


def build_message(
    level: str,
    hostname: str,
    alerts: list,
    processes: list,
    os_name: str = "linux",
    disks: list = None,
    # Extended metrics
    ip_addresses: list = None,
    cpu_count: int = 0,
    ram_total_gb: float = 0,
    ram_used_gb: float = 0,
    swap_percent: float = 0,
    swap_used_gb: float = 0,
    swap_total_gb: float = 0,
    disk_io: dict = None,
) -> str:
    """Build an HTML-formatted alert message for Telegram."""
    now      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon     = "🔴" if level == "CRITICAL" else "⚠️"
    os_badge = "🪟 Windows" if os_name == "windows" else "🐧 Linux"
    ip_str   = "  ".join(ip_addresses) if ip_addresses else ""

    lines = [
        f"{icon} <b>[{level}] {hostname}</b>  <i>{os_badge}</i>",
        f"🕐 <code>{now}</code>",
    ]
    if ip_str:
        lines.append(f"🌐 <code>{ip_str}</code>")

    # ── System specs summary ────────────────────────────────────
    spec_parts = []
    if cpu_count:
        spec_parts.append(f"CPU cores: <code>{cpu_count}</code>")
    if ram_total_gb:
        spec_parts.append(f"RAM: <code>{ram_used_gb}GB / {ram_total_gb}GB</code>")
    if swap_total_gb:
        swap_label = "Pagefile" if os_name == "windows" else "Swap"
        spec_parts.append(f"{swap_label}: <code>{swap_used_gb}GB / {swap_total_gb}GB ({swap_percent:.1f}%)</code>")
    if disk_io:
        spec_parts.append(
            f"Disk I/O: <code>R {disk_io.get('read_mbps', 0):.1f} MB/s "
            f"/ W {disk_io.get('write_mbps', 0):.1f} MB/s</code>"
        )
    if spec_parts:
        lines.append("")
        lines.append("🖥️ <b>System Info:</b>")
        for sp in spec_parts:
            lines.append(f"  {sp}")

    # ── Alerts ──────────────────────────────────────────────────
    lines.append("")
    lines.append("📊 <b>Resource thresholds exceeded:</b>")
    for alert in alerts:
        lines.append(f"  • {alert}")

    # ── Per-drive disk detail (Windows) ─────────────────────────
    if os_name == "windows" and disks:
        lines.append("")
        lines.append("💾 <b>Disk Usage per Drive:</b>")
        drive_rows = [f"{'Drive':<8} {'Used':>8} {'Total':>8} {'Free':>8} {'%':>6}"]
        drive_rows.append("─" * 44)
        for d in disks:
            flag = " ⚠️" if d["percent"] > 80 else ""
            drive_rows.append(
                f"{d['mount']:<8} {d['used_gb']:>6.1f}GB {d['total_gb']:>6.1f}GB "
                f"{d['free_gb']:>6.1f}GB {d['percent']:>5.1f}%{flag}"
            )
        nl = "\n"
        lines.append(f"<pre>{nl.join(drive_rows)}</pre>")

    # ── Top processes ────────────────────────────────────────────
    if processes:
        lines.append("")
        lines.append("⚙️ <b>Top resource-consuming processes:</b>")
        lines.append(f"<pre>{format_process_table(processes)}</pre>")

    lines.append("─" * 25)
    lines.append("🤖 <i>Linux Monitor System</i>")

    return "\n".join(lines)


def evaluate_metrics(metrics: dict):
    hostname      = metrics.get("hostname", "Unknown")
    os_name       = metrics.get("os", "linux").lower()
    ip_addresses  = metrics.get("ip_addresses", [])
    cpu           = metrics.get("cpu_percent", 0)
    cpu_count     = metrics.get("cpu_count", 0)
    ram           = metrics.get("ram_percent", 0)
    ram_total_gb  = metrics.get("ram_total_gb", 0)
    ram_used_gb   = metrics.get("ram_used_gb", 0)
    swap_percent  = metrics.get("swap_percent", 0)
    swap_total_gb = metrics.get("swap_total_gb", 0)
    swap_used_gb  = metrics.get("swap_used_gb", 0)
    disk          = metrics.get("disk_percent", 0)
    load          = metrics.get("load_avg_1", 0)
    processes     = metrics.get("top_processes", [])
    disks         = metrics.get("disks", [])
    disk_io       = metrics.get("disk_io", {})

    alerts = []
    level  = "OK"

    # ── Critical (> 95%) ──────────────────────────────────────────
    if cpu > 95 or ram > 95 or disk > 95:
        level = "CRITICAL"
        if cpu  > 95: alerts.append(f"🔴 CPU:  <code>{cpu}%</code>  <i>(Critical &gt; 95%)</i>")
        if ram  > 95:
            ram_info = f"{ram}% of {ram_total_gb}GB" if ram_total_gb else f"{ram}%"
            alerts.append(f"🔴 RAM:  <code>{ram_info}</code>  <i>(Critical &gt; 95%)</i>")
        if disk > 95: alerts.append(f"🔴 Disk: <code>{disk}%</code> <i>(Critical &gt; 95%)</i>")

    # ── Warning (> 80%) ───────────────────────────────────────────
    elif cpu > 80 or ram > 80 or disk > 80:
        level = "WARNING"
        if cpu  > 80: alerts.append(f"⚠️ CPU:  <code>{cpu}%</code>  <i>(Warning &gt; 80%)</i>")
        if ram  > 80:
            ram_info = f"{ram}% of {ram_total_gb}GB" if ram_total_gb else f"{ram}%"
            alerts.append(f"⚠️ RAM:  <code>{ram_info}</code>  <i>(Warning &gt; 80%)</i>")
        if disk > 80: alerts.append(f"⚠️ Disk: <code>{disk}%</code> <i>(Warning &gt; 80%)</i>")

    # ── Load Average (Linux) / CPU Rolling Avg (Windows) ─────────
    if load > 2:
        if level == "OK":
            level = "WARNING"
        label = "CPU Avg" if os_name == "windows" else "Load Avg"
        core_info = f" / {cpu_count} cores" if cpu_count else ""
        alerts.append(f"📈 {label}: <code>{load:.2f}{core_info}</code> <i>(High &gt; 2.0)</i>")

    # ── Swap / Pagefile alert (> 70% when RAM is also high) ───────
    swap_label = "Pagefile" if os_name == "windows" else "Swap"
    if swap_percent > 70 and ram > 80:
        if level == "OK":
            level = "WARNING"
        alerts.append(
            f"💾 {swap_label}: <code>{swap_percent:.1f}% ({swap_used_gb}GB / {swap_total_gb}GB)</code>"
            f"  <i>(High — risk of OOM / disk thrashing)</i>"
        )

    if alerts:
        message = build_message(
            level, hostname, alerts, processes,
            os_name       = os_name,
            disks         = disks,
            ip_addresses  = ip_addresses,
            cpu_count     = cpu_count,
            ram_total_gb  = ram_total_gb,
            ram_used_gb   = ram_used_gb,
            swap_percent  = swap_percent,
            swap_used_gb  = swap_used_gb,
            swap_total_gb = swap_total_gb,
            disk_io       = disk_io,
        )
        print(f"Sending {level} alert for {hostname} [{os_name}]...", flush=True)
        notifier.send_alert(message)
    else:
        swap_str = f" Swap:{swap_percent:.1f}%" if swap_percent else ""
        print(
            f"[{hostname}] OK — CPU:{cpu}% RAM:{ram}%({ram_used_gb}GB/{ram_total_gb}GB) "
            f"Disk:{disk}%{swap_str} "
            f"{'CPUAvg' if os_name == 'windows' else 'Load'}:{load:.2f}"
            + (f"/{cpu_count}c" if cpu_count else ""),
            flush=True
        )
