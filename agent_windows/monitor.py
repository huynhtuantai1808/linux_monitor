import os
import sys
import time
import socket
import logging
import collections
import psutil
import requests
from dotenv import load_dotenv

# Load configuration from .env file in the same directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Flush stdout immediately — required for nohup / Windows service log visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

MASTER_URL     = os.environ.get("MASTER_URL", "http://127.0.0.1:8000/metrics")
INTERVAL       = int(os.environ.get("INTERVAL", 60))
# Normalize drive letters: strip whitespace, colon, make uppercase  ("C:" → "C", "c" → "C")
MONITOR_DRIVES = [d.strip().upper().rstrip(":") for d in os.environ.get("MONITOR_DRIVES", "").split(",") if d.strip()]

# Rolling buffer to compute CPU average over 1 / 5 / 15 samples (simulates load average)
_cpu_history: collections.deque = collections.deque(maxlen=15)

# Disk I/O delta tracking
_prev_disk_io      = None
_prev_disk_io_time = None


def get_ip_addresses() -> list[str]:
    """Return all non-loopback IPv4 addresses of this machine."""
    ips = []
    try:
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ips.append(addr.address)
    except Exception:
        pass
    return ips if ips else ["unknown"]


def get_drives() -> list[str]:
    """Return list of drive mount points to monitor (e.g. ['C:\\\\', 'E:\\\\'])."""
    partitions = psutil.disk_partitions(all=False)
    drives = []
    for p in partitions:
        # Skip CD-ROM / removable drives that may error on disk_usage()
        if "cdrom" in p.opts.lower() or p.fstype == "":
            continue
        if MONITOR_DRIVES:
            # Normalize device letter: "C:\\" → "C"
            letter = p.device.replace("\\", "").replace("/", "").rstrip(":").upper()
            if letter not in MONITOR_DRIVES:
                log.debug(f"Skipping drive {p.device!r} (not in MONITOR_DRIVES={MONITOR_DRIVES})")
                continue
        drives.append(p.mountpoint)
    if not drives:
        log.warning(f"No drives matched MONITOR_DRIVES={MONITOR_DRIVES}. Check .env spelling.")
    else:
        log.debug(f"Monitoring drives: {drives}")
    return drives


def get_disk_summary(drives: list[str]) -> tuple[float, list[dict]]:
    """
    Returns:
        max_percent  – highest disk usage % across all monitored drives
        drive_list   – per-drive detail list
    """
    drive_list  = []
    max_percent = 0.0
    for mount in drives:
        try:
            usage = psutil.disk_usage(mount)
            pct   = usage.percent
            drive_list.append({
                "mount":    mount,
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb":  round(usage.used  / (1024 ** 3), 1),
                "free_gb":  round(usage.free  / (1024 ** 3), 1),
                "percent":  pct,
            })
            if pct > max_percent:
                max_percent = pct
        except PermissionError:
            log.warning(f"Permission denied reading disk: {mount}")
    return max_percent, drive_list


def get_disk_io() -> dict:
    """Calculate disk I/O rate (MB/s) since last call."""
    global _prev_disk_io, _prev_disk_io_time
    try:
        current = psutil.disk_io_counters()
        now     = time.time()
        if _prev_disk_io is None or current is None:
            _prev_disk_io      = current
            _prev_disk_io_time = now
            return {"read_mbps": 0.0, "write_mbps": 0.0}
        elapsed = now - _prev_disk_io_time
        if elapsed <= 0:
            return {"read_mbps": 0.0, "write_mbps": 0.0}
        read_mbps  = (current.read_bytes  - _prev_disk_io.read_bytes)  / elapsed / (1024 ** 2)
        write_mbps = (current.write_bytes - _prev_disk_io.write_bytes) / elapsed / (1024 ** 2)
        _prev_disk_io      = current
        _prev_disk_io_time = now
        return {
            "read_mbps":  round(max(0.0, read_mbps),  2),
            "write_mbps": round(max(0.0, write_mbps), 2),
        }
    except Exception:
        return {"read_mbps": 0.0, "write_mbps": 0.0}


def get_top_processes(sort_by: str = "cpu", limit: int = 5) -> list[dict]:
    """Return top N processes with CPU%, RAM%, and absolute RAM (MB)."""
    procs = []
    for proc in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent", "memory_info"]
    ):
        try:
            info = proc.info.copy()
            rss  = (info.get("memory_info") and info["memory_info"].rss) or 0
            info["ram_mb"] = round(rss / (1024 ** 2), 1)
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda p: p.get(key, 0) or 0, reverse=True)
    return procs[:limit]


def get_cpu_rolling_avg() -> tuple[float, float, float]:
    """
    Simulate Linux load average using rolling CPU history.
    Returns (avg_1, avg_5, avg_15) based on last 1/5/15 samples.
    Note: On Windows, load average is not a native metric.
          This approximation uses recent CPU% samples.
    """
    history = list(_cpu_history)
    n = len(history)

    def avg(samples):
        return round(sum(samples) / len(samples), 2) if samples else 0.0

    avg1  = avg(history[max(0, n - 1):])
    avg5  = avg(history[max(0, n - 5):])
    avg15 = avg(history)
    return avg1, avg5, avg15


def collect_metrics() -> dict:
    hostname  = socket.gethostname()
    cpu_count = psutil.cpu_count(logical=True) or 1

    # CPU (measure over 1 second)
    cpu_percent = psutil.cpu_percent(interval=1)
    _cpu_history.append(cpu_percent)

    # RAM
    ram_info     = psutil.virtual_memory()
    ram_percent  = ram_info.percent
    ram_total_gb = round(ram_info.total / (1024 ** 3), 1)
    ram_used_gb  = round(ram_info.used  / (1024 ** 3), 1)

    # Pagefile (Windows equivalent of Swap)
    swap          = psutil.swap_memory()
    swap_percent  = swap.percent
    swap_total_gb = round(swap.total / (1024 ** 3), 1)
    swap_used_gb  = round(swap.used  / (1024 ** 3), 1)

    # Disk — all monitored drives
    drives               = get_drives()
    disk_percent, disks  = get_disk_summary(drives)

    # Disk I/O
    disk_io = get_disk_io()

    # CPU rolling average (Windows substitute for load average)
    avg1, avg5, avg15 = get_cpu_rolling_avg()

    metrics = {
        "hostname":      hostname,
        "ip_addresses":  get_ip_addresses(),
        "os":            "windows",
        "cpu_percent":   cpu_percent,
        "cpu_count":     cpu_count,
        "ram_percent":   ram_percent,
        "ram_total_gb":  ram_total_gb,
        "ram_used_gb":   ram_used_gb,
        "swap_percent":  swap_percent,         # Pagefile usage
        "swap_total_gb": swap_total_gb,
        "swap_used_gb":  swap_used_gb,
        "disk_percent":  disk_percent,          # Max across all drives
        "disks":         disks,                 # Per-drive detail
        "load_avg_1":    avg1,                  # Rolling CPU avg (1 sample)
        "load_avg_5":    avg5,                  # Rolling CPU avg (5 samples)
        "load_avg_15":   avg15,                 # Rolling CPU avg (15 samples)
        "disk_io":       disk_io,
        "top_processes": [],
    }

    # Attach top processes when any threshold is exceeded
    if cpu_percent > 80:
        metrics["top_processes"] = get_top_processes(sort_by="cpu", limit=5)
    elif ram_percent > 80:
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=5)
    elif disk_percent > 80:
        # Disk pressure is not always process-driven, log top memory consumers for reference
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=3)

    return metrics


def main():
    log.info(f"Windows Agent started. Sending metrics to {MASTER_URL} every {INTERVAL} seconds.")
    log.info(f"Monitored drives: {MONITOR_DRIVES if MONITOR_DRIVES else 'All available drives'}")
    log.info(f"CPU cores: {psutil.cpu_count(logical=True)}")

    while True:
        try:
            metrics  = collect_metrics()
            response = requests.post(MASTER_URL, json=metrics, timeout=10)
            if response.status_code == 200:
                log.info(
                    f"Metrics sent — "
                    f"CPU:{metrics['cpu_percent']}% "
                    f"RAM:{metrics['ram_percent']}% ({metrics['ram_used_gb']}GB/{metrics['ram_total_gb']}GB) "
                    f"Disk:{metrics['disk_percent']}% "
                    f"Pagefile:{metrics['swap_percent']}% "
                    f"IO R:{metrics['disk_io']['read_mbps']}MB/s W:{metrics['disk_io']['write_mbps']}MB/s"
                )
            else:
                log.warning(f"Failed to send metrics: HTTP {response.status_code} — {response.text}")
        except Exception as e:
            log.error(f"Connection error to Master: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
