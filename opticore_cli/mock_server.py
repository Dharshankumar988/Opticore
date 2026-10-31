"""Standalone OptiCore mock server for local testing and validation.

Faithfully implements the REST and WebSocket endpoints of the OptiCore Vision API
from the notebook source of truth, generating realistic synthetic events.
"""

import asyncio
import time
from collections import deque
from typing import Dict, List, Optional
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="OptiCore Mock Vision API", version="1.2.0")

SERVER_START_TIME = time.time()
ALERT_HISTORY = deque(maxlen=200)
PRODUCER_ACTIVE = False
PRODUCER_ID = None

DEMO_CLASSES = [
    ("car", 1, "ahead", True, "head-on", "P1", 86.5, "A car appears to be approaching ahead."),
    ("pothole", 1, "ahead", False, None, "P1", 81.0, "Pothole detected ahead."),
    ("bus", 1, "left", True, "from your left", "P1", 79.2, "A bus appears to be approaching from your left."),
    ("truck", 1, "right", True, "from your right", "P1", 83.4, "A truck appears to be approaching from your right."),
    ("person", 2, "left", False, None, "P2", 62.0, "Person detected on your left."),
    ("motorcycle", 2, "right", True, "from your right", "P2", 68.5, "Motorcycle detected on your right."),
    ("stairs", 3, "ahead", False, None, "P3", 45.0, "Stairs detected ahead."),
    ("door", 4, "ahead", False, None, "P3", 38.0, "Door detected ahead."),
    ("obstacle", 3, "right", False, None, "P3", 42.0, "Obstacle detected on your right."),
]

mock_track_counter = 1
mock_frame_counter = 0


def generate_synthetic_alert() -> Dict:
    global mock_track_counter
    import random
    choice = random.choice(DEMO_CLASSES)
    name, class_prio, pos, approaching, app_dir, prio, base_risk, msg = choice

    track_id = mock_track_counter
    mock_track_counter = (mock_track_counter % 25) + 1

    alert = {
        "timestamp": time.time(),
        "track_id": track_id,
        "name": name,
        "confidence": round(random.uniform(0.72, 0.96), 3),
        "class_priority": class_prio,
        "position": pos,
        "approaching": approaching,
        "approach_direction": app_dir,
        "priority": prio,
        "risk_score": round(base_risk + random.uniform(-3.0, 3.0), 1),
        "message": msg,
    }
    ALERT_HISTORY.appendleft(alert)
    return alert


# Seed with a few initial events
for _ in range(5):
    generate_synthetic_alert()


@app.get("/")
async def root():
    return HTMLResponse("<html><body><h1>OptiCore Mock Server</h1><p>Running</p></body></html>")


@app.get("/health")
async def health():
    global mock_frame_counter
    mock_frame_counter += 1
    return {
        "status": "ok",
        "model_loaded": True,
        "device": "mock-cuda:0",
        "classes": 80,
        "tracker": "bytetrack.yaml",
        "imgsz": 640,
        "frames_processed": mock_frame_counter,
        "last_inference_ms": 32.4,
        "avg_inference_ms": 31.8,
        "fps_ema": 30.5,
        "frames_rejected": 0,
        "last_inference_unix": time.time(),
    }


@app.get("/status")
async def status():
    return {
        "service": "OptiCore Vision API",
        "version": "1.2.0",
        "model_loaded": True,
        "device": "mock-cuda:0",
        "gpu_available": True,
        "gpu_name": "NVIDIA GeForce RTX 4090 (Mock)",
        "producer_active": PRODUCER_ACTIVE,
        "producer_id": PRODUCER_ID,
        "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
        "metrics": {
            "frames_processed": mock_frame_counter,
            "last_inference_ms": 32.4,
            "avg_inference_ms": 31.8,
            "fps_ema": 30.5,
            "frames_rejected": 0,
            "last_inference_unix": time.time(),
        },
        "priority_engine": "class priority + image-only risk heuristic",
        "speech_policy": "browser speech + track-level server deduplication",
    }


@app.get("/metrics")
async def metrics():
    return {
        "frames_processed": mock_frame_counter,
        "last_inference_ms": 32.4,
        "avg_inference_ms": 31.8,
        "fps_ema": 30.5,
        "frames_rejected": 0,
        "last_inference_unix": time.time(),
    }


@app.get("/events")
async def events(limit: int = 20):
    clamped_limit = max(1, min(100, int(limit)))
    # Occasionally generate a new synthetic alert so polling sees new events
    import random
    if random.random() < 0.65:
        generate_synthetic_alert()

    recent = list(ALERT_HISTORY)[:clamped_limit]
    return {"events": recent}


@app.websocket("/ws/video")
async def video_ws(websocket: WebSocket):
    global PRODUCER_ACTIVE, PRODUCER_ID
    await websocket.accept()
    if PRODUCER_ACTIVE:
        await websocket.send_text('{"type":"error","code":"producer_busy","message":"Another camera stream is active."}')
        await websocket.close(code=1013)
        return

    PRODUCER_ACTIVE = True
    PRODUCER_ID = "mock-stream-1"
    try:
        while True:
            data = await websocket.receive_bytes()
            alert = generate_synthetic_alert()
            resp = {
                "image": "",
                "detections": [alert],
                "counts": {"current": {alert["name"]: 1}, "unique_tracked": {alert["name"]: 1}},
                "alerts": [alert],
                "inference_ms": 31.5,
                "stream_id": PRODUCER_ID,
                "timestamp": time.time(),
            }
            import json
            await websocket.send_text(json.dumps(resp))
    except WebSocketDisconnect:
        pass
    finally:
        PRODUCER_ACTIVE = False
        PRODUCER_ID = None


def run_mock_server(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OptiCore Mock Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    args = parser.parse_args()
    print(f"Starting OptiCore Mock Server on http://{args.host}:{args.port}")
    run_mock_server(host=args.host, port=args.port)
