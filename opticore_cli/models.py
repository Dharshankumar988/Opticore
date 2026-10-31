"""Data models representing OptiCore server entities and detection events.

These models strictly adhere to the schemas defined in the OptiCore FastAPI server.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ServerHealth:
    """Represents the response from GET /health."""
    status: str
    model_loaded: bool
    device: str
    classes: int
    tracker: str
    imgsz: int
    frames_processed: int = 0
    last_inference_ms: float = 0.0
    avg_inference_ms: float = 0.0
    fps_ema: float = 0.0
    frames_rejected: int = 0
    last_inference_unix: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerHealth":
        return cls(
            status=str(data.get("status", "unknown")),
            model_loaded=bool(data.get("model_loaded", False)),
            device=str(data.get("device", "unknown")),
            classes=int(data.get("classes", 0)),
            tracker=str(data.get("tracker", "")),
            imgsz=int(data.get("imgsz", 0)),
            frames_processed=int(data.get("frames_processed", 0)),
            last_inference_ms=float(data.get("last_inference_ms", 0.0)),
            avg_inference_ms=float(data.get("avg_inference_ms", 0.0)),
            fps_ema=float(data.get("fps_ema", 0.0)),
            frames_rejected=int(data.get("frames_rejected", 0)),
            last_inference_unix=data.get("last_inference_unix"),
            raw=data,
        )


@dataclass
class ServerStatus:
    """Represents the response from GET /status."""
    service: str
    version: str
    model_loaded: bool
    device: str
    gpu_available: bool
    gpu_name: Optional[str]
    producer_active: bool
    producer_id: Optional[str]
    uptime_seconds: float
    metrics: Dict[str, Any]
    priority_engine: str
    speech_policy: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerStatus":
        return cls(
            service=str(data.get("service", "OptiCore Vision API")),
            version=str(data.get("version", "unknown")),
            model_loaded=bool(data.get("model_loaded", False)),
            device=str(data.get("device", "unknown")),
            gpu_available=bool(data.get("gpu_available", False)),
            gpu_name=data.get("gpu_name"),
            producer_active=bool(data.get("producer_active", False)),
            producer_id=data.get("producer_id"),
            uptime_seconds=float(data.get("uptime_seconds", 0.0)),
            metrics=data.get("metrics", {}),
            priority_engine=str(data.get("priority_engine", "")),
            speech_policy=str(data.get("speech_policy", "")),
            raw=data,
        )


@dataclass
class ServerMetrics:
    """Represents the response from GET /metrics."""
    frames_processed: int
    last_inference_ms: float
    avg_inference_ms: float
    fps_ema: float
    frames_rejected: int
    last_inference_unix: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerMetrics":
        return cls(
            frames_processed=int(data.get("frames_processed", 0)),
            last_inference_ms=float(data.get("last_inference_ms", 0.0)),
            avg_inference_ms=float(data.get("avg_inference_ms", 0.0)),
            fps_ema=float(data.get("fps_ema", 0.0)),
            frames_rejected=int(data.get("frames_rejected", 0)),
            last_inference_unix=data.get("last_inference_unix"),
        )


@dataclass
class DetectionEvent:
    """Represents an alert event item from GET /events."""
    timestamp: float
    track_id: Optional[int]
    name: str
    confidence: float
    class_priority: int
    position: str
    approaching: bool
    approach_direction: Optional[str]
    priority: str
    risk_score: float
    message: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_time(self) -> str:
        if not self.timestamp:
            return "--:--:--"
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%H:%M:%S.%f")[:-3]

    @property
    def tracking_id_display(self) -> str:
        if self.track_id is None:
            return "untracked"
        return f"#{self.track_id}"

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.1f}%"

    @property
    def movement_display(self) -> str:
        if self.approaching:
            if self.approach_direction:
                return f"Approaching ({self.approach_direction})"
            return "Approaching"
        return "Stationary / Lateral"

    @property
    def event_key(self) -> str:
        """Deduplication key for this event instance."""
        return f"{self.timestamp:.3f}_{self.track_id}_{self.name}_{self.priority}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectionEvent":
        return cls(
            timestamp=float(data.get("timestamp", 0.0)),
            track_id=int(data["track_id"]) if data.get("track_id") is not None else None,
            name=str(data.get("name", "unknown")).lower(),
            confidence=float(data.get("confidence", 0.0)),
            class_priority=int(data.get("class_priority", 7)),
            position=str(data.get("position", "ahead")),
            approaching=bool(data.get("approaching", False)),
            approach_direction=data.get("approach_direction"),
            priority=str(data.get("priority", "P4")),
            risk_score=float(data.get("risk_score", 0.0)),
            message=str(data.get("message", "")),
            raw=data,
        )


@dataclass
class ConnectionResult:
    """Result of connection test / ping."""
    ok: bool
    url: str
    latency_ms: float = 0.0
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    health: Optional[ServerHealth] = None
    status: Optional[ServerStatus] = None
