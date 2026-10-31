"""Pytest configuration and shared fixtures for OptiCore CLI tests."""

import pytest
import uvicorn
import threading
import time
from opticore_cli.mock_server import app


@pytest.fixture(scope="session")
def mock_server_port():
    return 8765


@pytest.fixture(scope="session")
def mock_server_url(mock_server_port):
    return f"http://127.0.0.1:{mock_server_port}"


@pytest.fixture(scope="session", autouse=True)
def live_mock_server(mock_server_port):
    """Starts a live instance of the mock OptiCore server on a dedicated test port."""
    config = uvicorn.Config(app=app, host="127.0.0.1", port=mock_server_port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be responsive
    import requests
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{mock_server_port}/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    yield

    server.should_exit = True
