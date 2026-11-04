"""Tests for stream_camera URL conversion, camera detection, and configuration integration."""

from opticore_cli.camera import detect_cameras
from stream_camera import convert_to_ws_url


def test_convert_to_ws_url():
    # HTTPS ngrok URL
    assert convert_to_ws_url("https://abc.ngrok-free.app") == "wss://abc.ngrok-free.app/ws/video"
    assert convert_to_ws_url("https://abc.ngrok-free.app/") == "wss://abc.ngrok-free.app/ws/video"

    # HTTP localhost
    assert convert_to_ws_url("http://127.0.0.1:8000") == "ws://127.0.0.1:8000/ws/video"

    # Already has ws/wss scheme
    assert convert_to_ws_url("wss://abc.ngrok-free.app/ws/video") == "wss://abc.ngrok-free.app/ws/video"
    assert convert_to_ws_url("ws://localhost:8000/ws/video") == "ws://localhost:8000/ws/video"

    # Plain host
    assert convert_to_ws_url("abc.ngrok-free.app") == "wss://abc.ngrok-free.app/ws/video"


def test_detect_cameras():
    cams = detect_cameras(max_probe=2)
    assert isinstance(cams, list)
    for c in cams:
        assert "index" in c
        assert "resolution" in c
        assert "label" in c


def test_stream_camera_voice_flags():
    import argparse
    from opticore_cli.config import ConfigManager

    config = ConfigManager().load()
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", dest="voice", action="store_true", default=config.voice_enabled)
    parser.add_argument("--no-voice", dest="voice", action="store_false")

    # Flag --voice
    args = parser.parse_args(["--voice"])
    assert args.voice is True

    # Flag --no-voice
    args = parser.parse_args(["--no-voice"])
    assert args.voice is False
