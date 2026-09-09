from notifier import Notifier

# Kênh cảnh báo được đọc tự động từ file .env (NOTIFY_CHANNEL)
notifier = Notifier()

def format_process_list(processes):
    if not processes:
        return "Không có thông tin tiến trình."
    
    text = "Các process tốn tài nguyên nhất:\n"
    for p in processes:
        text += f"- PID: {p.get('pid')} | Tên: {p.get('name')} | User: {p.get('username')} | CPU: {p.get('cpu_percent')}% | RAM: {p.get('memory_percent', 0):.2f}%\n"
    return text

def evaluate_metrics(metrics):
    hostname = metrics.get("hostname", "Unknown")
    cpu = metrics.get("cpu_percent", 0)
    ram = metrics.get("ram_percent", 0)
    disk = metrics.get("disk_percent", 0)
    load = metrics.get("load_avg_1", 0)
    processes = metrics.get("top_processes", [])

    alerts = []
    level = "OK"

    # Đánh giá Critical (> 95%)
    if cpu > 95 or ram > 95 or disk > 95:
        level = "CRITICAL"
        if cpu > 95: alerts.append(f"CPU usage is CRITICAL: {cpu}%")
        if ram > 95: alerts.append(f"RAM usage is CRITICAL: {ram}%")
        if disk > 95: alerts.append(f"Disk usage is CRITICAL: {disk}%")
    
    # Đánh giá Warning (> 80%)
    elif cpu > 80 or ram > 80 or disk > 80:
        level = "WARNING"
        if cpu > 80: alerts.append(f"CPU usage is HIGH: {cpu}%")
        if ram > 80: alerts.append(f"RAM usage is HIGH: {ram}%")
        if disk > 80: alerts.append(f"Disk usage is HIGH: {disk}%")

    # Đánh giá Load Average
    if load > 2:
        if level == "OK": level = "WARNING"
        alerts.append(f"Load Average is HIGH: {load}")

    if alerts:
        process_text = format_process_list(processes)
        message = f"[{level}] Cảnh báo từ Server: {hostname}\n"
        message += "\n".join(alerts) + "\n\n"
        message += process_text
        
        # Gửi cảnh báo
        print(f"Đang gửi cảnh báo {level} cho {hostname}...")
        notifier.send_alert(message)
    else:
        print(f"[{hostname}] Metrics OK.")
