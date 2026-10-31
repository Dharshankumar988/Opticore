"""Tests for data models parsing and properties."""

import time
from opticore_cli.models import DetectionEvent, ServerHealth, ServerMetrics, ServerStatus


def test_server_health_model():
    raw = {
        "status": "ok",
        "model_loaded": True,
        "device": "0",
        "classes": 80,
        "tracker": "bytetrack.yaml",
        "imgsz": 640,
        "frames_processed": 150,
        "last_inference_ms": 35.2,
        "avg_inference_ms": 34.0,
        "fps_ema": 29.4,
        "frames_rejected": 2,
        "last_inference_unix": 1730000000.0,
    }
    h = ServerHealth.from_dict(raw)
    assert h.status == "ok"
    assert h.model_loaded is True
    assert h.device == "0"
    assert h.classes == 80
    assert h.frames_processed == 150
    assert h.last_inference_ms == 35.2
    assert h.avg_inference_ms == 34.0
    assert h.fps_ema == 29.4
    assert h.frames_rejected == 2


def test_server_status_model():
    raw = {
        "service": "OptiCore Vision API",
        "version": "1.2.0",
        "model_loaded": True,
        "device": "0",
        "gpu_available": True,
        "gpu_name": "Tesla T4",
        "producer_active": False,
        "producer_id": None,
        "uptime_seconds": 360.5,
        "metrics": {"frames_processed": 10},
        "priority_engine": "class priority + image-only risk heuristic",
        "speech_policy": "browser speech + track-level server deduplication",
    }
    s = ServerStatus.from_dict(raw)
    assert s.service == "OptiCore Vision API"
    assert s.gpu_name == "Tesla T4"
    assert s.gpu_available is True
    assert s.producer_active is False
    assert s.uptime_seconds == 360.5


def test_server_metrics_model():
    raw = {
        "frames_processed": 50,
        "last_inference_ms": 28.5,
        "avg_inference_ms": 29.1,
        "fps_ema": 33.2,
        "frames_rejected": 1,
        "last_inference_unix": 1730000010.0,
    }
    m = ServerMetrics.from_dict(raw)
    assert m.frames_processed == 50
    assert m.last_inference_ms == 28.5
    assert m.fps_ema == 33.2


def test_detection_event_model():
    now = 1730000000.123
    raw = {
        "timestamp": now,
        "track_id": 4,
        "name": "car",
        "confidence": 0.887,
        "class_priority": 1,
        "position": "ahead",
        "approaching": True,
        "approach_direction": "head-on",
        "priority": "P1",
        "risk_score": 85.4,
        "message": "A car appears to be approaching ahead.",
    }
    e = DetectionEvent.from_dict(raw)
    assert e.name == "car"
    assert e.track_id == 4
    assert e.tracking_id_display == "#4"
    assert e.confidence_pct == "88.7%"
    assert e.approaching is True
    assert "Approaching (head-on)" in e.movement_display
    assert "P1" in e.event_key
    assert len(e.formatted_time) > 0


def test_detection_event_untracked():
    raw = {
        "timestamp": 1730000000.0,
        "track_id": None,
        "name": "obstacle",
        "confidence": 0.55,
        "class_priority": 3,
        "position": "left",
        "approaching": False,
        "approach_direction": None,
        "priority": "P3",
        "risk_score": 40.0,
        "message": "Obstacle detected on your left.",
    }
    e = DetectionEvent.from_dict(raw)
    assert e.tracking_id_display == "untracked"
    assert e.movement_display == "Stationary / Lateral"
