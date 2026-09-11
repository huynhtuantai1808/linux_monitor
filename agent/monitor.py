import os
import sys
import time
import socket
import logging
import psutil
import requests
from dotenv import load_dotenv

# Load configuration from .env file in the same directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Flush stdout immediately (no buffering) — required for nohup log visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

MASTER_URL = os.environ.get("MASTER_URL", "http://127.0.0.1:8000/metrics")
INTERVAL   = int(os.environ.get("INTERVAL", 60))

# Disk I/O delta tracking
_prev_disk_io      = None
_prev_disk_io_time = None


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


def get_top_processes(sort_by: str = "cpu", limit: int = 5) -> list:
    """Return top N processes with CPU%, RAM%, and absolute RAM (MB)."""
    total_ram = psutil.virtual_memory().total
    procs = []
    for proc in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent", "memory_info"]
    ):
        try:
            info = proc.info.copy()
            rss = (info.get("memory_info") and info["memory_info"].rss) or 0
            info["ram_mb"] = round(rss / (1024 ** 2), 1)
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda p: p.get(key) or 0, reverse=True)
    return procs[:limit]


def collect_metrics() -> dict:
    hostname  = socket.gethostname()
    cpu_count = psutil.cpu_count(logical=True) or 1

    # 1. CPU
    cpu_percent = psutil.cpu_percent(interval=1)

    # 2. RAM
    ram_info     = psutil.virtual_memory()
    ram_percent  = ram_info.percent
    ram_total_gb = round(ram_info.total / (1024 ** 3), 1)
    ram_used_gb  = round(ram_info.used  / (1024 ** 3), 1)

    # 3. Swap
    swap          = psutil.swap_memory()
    swap_percent  = swap.percent
    swap_total_gb = round(swap.total / (1024 ** 3), 1)
    swap_used_gb  = round(swap.used  / (1024 ** 3), 1)

    # 4. Disk (root partition)
    disk_info    = psutil.disk_usage("/")
    disk_percent = disk_info.percent

    # 5. Load Average (Linux only)
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0

    # 6. Disk I/O
    disk_io = get_disk_io()

    metrics = {
        "hostname":      hostname,
        "os":            "linux",
        "cpu_percent":   cpu_percent,
        "cpu_count":     cpu_count,
        "ram_percent":   ram_percent,
        "ram_total_gb":  ram_total_gb,
        "ram_used_gb":   ram_used_gb,
        "swap_percent":  swap_percent,
        "swap_total_gb": swap_total_gb,
        "swap_used_gb":  swap_used_gb,
        "disk_percent":  disk_percent,
        "load_avg_1":    load1,
        "load_avg_5":    load5,
        "load_avg_15":   load15,
        "disk_io":       disk_io,
        "top_processes": [],
    }

    # Collect top processes if any resource exceeds threshold
    if cpu_percent > 80 or load1 > 2:
        metrics["top_processes"] = get_top_processes(sort_by="cpu", limit=5)
    elif ram_percent > 80:
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=5)
    elif disk_percent > 80:
        # Disk usage is not always process-driven, but log top memory consumers for reference
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=3)

    return metrics


def main():
    log.info(f"Agent started. Sending metrics to {MASTER_URL} every {INTERVAL} seconds.")
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
                    f"Load:{metrics['load_avg_1']:.2f}/{metrics['cpu_count']}cores "
                    f"IO R:{metrics['disk_io']['read_mbps']}MB/s W:{metrics['disk_io']['write_mbps']}MB/s"
                )
            else:
                log.warning(f"Failed to send metrics: HTTP {response.status_code} — {response.text}")
        except Exception as e:
            log.error(f"Connection error to Master: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
