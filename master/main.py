#!/usr/bin/env python3
"""
Linux Monitor - Master Server
Entry point: python main.py
Configure via the .env file in the same directory
"""
import os
from dotenv import load_dotenv

# Load .env before importing other modules
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

import uvicorn
from fastapi import FastAPI, Request
from alerter import evaluate_metrics

app = FastAPI(
    title="Linux Monitor - Master Server",
    description="API for receiving metrics from Agents and sending alerts",
    version="1.0.0",
)

@app.get("/health")
async def health_check():
    """Endpoint to verify the Master server is running"""
    return {"status": "ok", "service": "Linux Monitor Master"}

@app.post("/metrics")
async def receive_metrics(request: Request):
    """Endpoint for receiving metrics from Agents"""
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
    print(f"  Listening address  : http://{host}:{port}")
    print(f"  Health check       : http://{host}:{port}/health")
    print(f"  Receive metrics    : POST http://{host}:{port}/metrics")
    print(f"  Alert channels     : {os.environ.get('NOTIFY_CHANNELS', 'telegram')}")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port)
