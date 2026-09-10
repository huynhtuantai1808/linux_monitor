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
MONITOR_DRIVES = [d.strip().upper() for d in os.environ.get("MONITOR_DRIVES", "").split(",") if d.strip()]

# Rolling buffer to compute CPU average over 1 / 5 / 15 samples (simulates load average)
_cpu_history: collections.deque = collections.deque(maxlen=15)


def get_drives() -> list[str]:
    """Return list of drive mount points to monitor (e.g. ['C:\\\\', 'D:\\\\'])."""
    partitions = psutil.disk_partitions(all=False)
    drives = []
    for p in partitions:
        # Skip CD-ROM / removable drives that may error on disk_usage()
        if "cdrom" in p.opts.lower() or p.fstype == "":
            continue
        if MONITOR_DRIVES:
            letter = p.device.replace("\\", "").replace("/", "").rstrip(":")
            if letter.upper() not in MONITOR_DRIVES:
                continue
        drives.append(p.mountpoint)
    return drives


def get_disk_summary(drives: list[str]) -> tuple[float, list[dict]]:
    """
    Returns:
        max_percent  – highest disk usage % across all monitored drives
        drive_list   – per-drive detail list
    """
    drive_list = []
    max_percent = 0.0
    for mount in drives:
        try:
            usage = psutil.disk_usage(mount)
            pct   = usage.percent
            drive_list.append({
                "mount":        mount,
                "total_gb":     round(usage.total / (1024 ** 3), 1),
                "used_gb":      round(usage.used  / (1024 ** 3), 1),
                "free_gb":      round(usage.free  / (1024 ** 3), 1),
                "percent":      pct,
            })
            if pct > max_percent:
                max_percent = pct
        except PermissionError:
            log.warning(f"Permission denied reading disk: {mount}")
    return max_percent, drive_list


def get_top_processes(sort_by: str = "cpu", limit: int = 5) -> list[dict]:
    """Return top N processes sorted by CPU or memory usage."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            procs.append(proc.info)
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
    hostname = socket.gethostname()

    # CPU (measure over 1 second)
    cpu_percent = psutil.cpu_percent(interval=1)
    _cpu_history.append(cpu_percent)

    # RAM
    ram_info    = psutil.virtual_memory()
    ram_percent = ram_info.percent

    # Disk — all monitored drives
    drives               = get_drives()
    disk_percent, disks  = get_disk_summary(drives)

    # CPU rolling average (Windows substitute for load average)
    avg1, avg5, avg15 = get_cpu_rolling_avg()

    metrics = {
        "hostname":      hostname,
        "os":            "windows",
        "cpu_percent":   cpu_percent,
        "ram_percent":   ram_percent,
        "disk_percent":  disk_percent,           # Max across all drives
        "disks":         disks,                  # Per-drive detail
        "load_avg_1":    avg1,                   # Rolling CPU avg (1 sample)
        "load_avg_5":    avg5,                   # Rolling CPU avg (5 samples)
        "load_avg_15":   avg15,                  # Rolling CPU avg (15 samples)
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

    while True:
        try:
            metrics  = collect_metrics()
            response = requests.post(MASTER_URL, json=metrics, timeout=10)
            if response.status_code == 200:
                log.info(
                    f"Metrics sent successfully — "
                    f"CPU:{metrics['cpu_percent']}% "
                    f"RAM:{metrics['ram_percent']}% "
                    f"Disk:{metrics['disk_percent']}%"
                )
            else:
                log.warning(f"Failed to send metrics: HTTP {response.status_code} — {response.text}")
        except Exception as e:
            log.error(f"Connection error to Master: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
