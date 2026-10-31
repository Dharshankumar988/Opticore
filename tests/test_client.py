"""Tests for OptiCore HTTP Client communicating with OptiCore API."""

import pytest
from opticore_cli.client import OptiCoreClient


def test_url_sanitization():
    # Strip spaces and trailing slashes
    assert OptiCoreClient.sanitize_url("  http://localhost:8000/  ") == "http://localhost:8000"

    # Auto-prepend http for standard hosts
    assert OptiCoreClient.sanitize_url("127.0.0.1:8000") == "http://127.0.0.1:8000"

    # Auto-prepend https and upgrade http for ngrok domains
    assert OptiCoreClient.sanitize_url("opticore-sub.ngrok-free.app") == "https://opticore-sub.ngrok-free.app"
    assert OptiCoreClient.sanitize_url("http://opticore-sub.ngrok-free.app/") == "https://opticore-sub.ngrok-free.app"


def test_client_ping_success(mock_server_url):
    client = OptiCoreClient(base_url=mock_server_url, timeout=3.0)
    res = client.ping()
    assert res.ok is True
    assert res.latency_ms > 0
    assert res.status_code == 200
    assert res.health is not None
    assert res.health.status == "ok"
    assert res.health.model_loaded is True
    assert res.status is not None
    assert res.status.service == "OptiCore Vision API"


def test_client_get_endpoints(mock_server_url):
    client = OptiCoreClient(base_url=mock_server_url, timeout=3.0)

    # Health
    health = client.get_health()
    assert health.status == "ok"
    assert health.classes == 80

    # Status
    status = client.get_status()
    assert status.version == "1.2.0"
    assert status.model_loaded is True

    # Metrics
    metrics = client.get_metrics()
    assert metrics.frames_processed >= 0
    assert metrics.last_inference_ms > 0

    # Events
    events = client.get_events(limit=10)
    assert isinstance(events, list)
    assert len(events) > 0
    assert events[0].name != ""


def test_client_connection_failure():
    # Point to an unused local port
    client = OptiCoreClient(base_url="http://127.0.0.1:54321", timeout=1.0)
    res = client.ping()
    assert res.ok is False
    assert any(term in res.error_message.lower() for term in ["refused", "failed", "timed out", "timeout"])


def test_client_headers():
    client = OptiCoreClient("http://127.0.0.1:8000")
    headers = client.session.headers
    assert "OptiCore-CLI" in headers.get("User-Agent", "")
    assert headers.get("ngrok-skip-browser-warning") == "69420"


def test_client_api_error_translation():
    from opticore_cli.client import OptiCoreAPIError
    # Client pointing to an unreachable port
    client = OptiCoreClient("http://127.0.0.1:54321", timeout=0.5)

    with pytest.raises(OptiCoreAPIError) as exc_info:
        client.get_health()

    err_text = str(exc_info.value).lower()
    assert any(term in err_text for term in ["connection refused", "network connection failed", "timed out", "dns resolution"])

