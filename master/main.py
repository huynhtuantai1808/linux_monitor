#!/usr/bin/env python3
"""
Linux Monitor - Master Server
Entry point: python main.py
Cấu hình tại file .env trong cùng thư mục
"""
import os
from dotenv import load_dotenv

# Load .env trước khi import các module khác
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

import uvicorn
from fastapi import FastAPI, Request
from alerter import evaluate_metrics

app = FastAPI(
    title="Linux Monitor - Master Server",
    description="API nhận metrics từ các Agent và gửi cảnh báo",
    version="1.0.0",
)

@app.get("/health")
async def health_check():
    """Endpoint kiểm tra Master đang hoạt động"""
    return {"status": "ok", "service": "Linux Monitor Master"}

@app.post("/metrics")
async def receive_metrics(request: Request):
    """Endpoint nhận metrics từ Agent"""
    try:
        metrics = await request.json()
        evaluate_metrics(metrics)
        return {"status": "success", "message": "Metrics received and evaluated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    host = os.environ.get("MASTER_HOST", "0.0.0.0")
    port = int(os.environ.get("MASTER_PORT", 8000))

    print("=" * 60)
    print("  Linux Monitor - Master Server")
    print("=" * 60)
    print(f"  Địa chỉ lắng nghe : http://{host}:{port}")
    print(f"  Health check       : http://{host}:{port}/health")
    print(f"  Nhận metrics       : POST http://{host}:{port}/metrics")
    print(f"  Kênh cảnh báo      : {os.environ.get('NOTIFY_CHANNEL', 'telegram')}")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port)
