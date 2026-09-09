from fastapi import FastAPI, Request
import uvicorn
from alerter import evaluate_metrics

app = FastAPI(title="Linux Monitor Master Server")

@app.post("/metrics")
async def receive_metrics(request: Request):
    metrics = await request.json()
    # Chuyển payload tới Engine đánh giá
    evaluate_metrics(metrics)
    return {"status": "success", "message": "Metrics received and evaluated"}

if __name__ == "__main__":
    print("Khởi động Master Server trên port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
