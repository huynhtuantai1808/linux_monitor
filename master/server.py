from fastapi import FastAPI, Request
import uvicorn
from alerter import evaluate_metrics

app = FastAPI(title="Linux Monitor Master Server")

@app.post("/metrics")
async def receive_metrics(request: Request):
    metrics = await request.json()
    # Forward payload to the evaluation engine
    evaluate_metrics(metrics)
    return {"status": "success", "message": "Metrics received and evaluated"}

if __name__ == "__main__":
    print("Starting Master Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
