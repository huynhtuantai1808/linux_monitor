import os
import time
import socket
import psutil
import requests
from dotenv import load_dotenv

# Load cấu hình từ file .env cùng thư mục
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MASTER_URL = os.environ.get("MASTER_URL", "http://127.0.0.1:8000/metrics")
INTERVAL = int(os.environ.get("INTERVAL", 60))

def get_top_processes(sort_by="cpu", limit=3):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if sort_by == "cpu":
        processes.sort(key=lambda p: p['cpu_percent'], reverse=True)
    elif sort_by == "memory":
        processes.sort(key=lambda p: p['memory_percent'], reverse=True)
    
    return processes[:limit]

def collect_metrics():
    hostname = socket.gethostname()
    
    # 1. CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # 2. RAM
    ram_info = psutil.virtual_memory()
    ram_percent = ram_info.percent
    
    # 3. Disk (Root partition)
    disk_info = psutil.disk_usage('/')
    disk_percent = disk_info.percent
    
    # 4. Load Average (Linux specific)
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0

    metrics = {
        "hostname": hostname,
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "disk_percent": disk_percent,
        "load_avg_1": load1,
        "load_avg_5": load5,
        "load_avg_15": load15,
        "top_processes": []
    }

    # Nếu bất kỳ tài nguyên nào > 80% hoặc load > 2, thu thập top process
    if cpu_percent > 80 or load1 > 2:
        metrics["top_processes"] = get_top_processes(sort_by="cpu", limit=5)
    elif ram_percent > 80:
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=5)
    elif disk_percent > 80:
        # Disk không hẳn do process hiện tại, nhưng vẫn log memory/cpu để tham khảo
        metrics["top_processes"] = get_top_processes(sort_by="memory", limit=3)

    return metrics

def main():
    print(f"Bắt đầu monitor agent. Gửi dữ liệu về {MASTER_URL} mỗi {INTERVAL} giây.")
    while True:
        try:
            metrics = collect_metrics()
            response = requests.post(MASTER_URL, json=metrics, timeout=10)
            if response.status_code == 200:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Đã gửi metrics thành công.")
            else:
                print(f"Lỗi khi gửi metrics: HTTP {response.status_code}")
        except Exception as e:
            print(f"Lỗi kết nối đến Master: {e}")
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
