"""Tests for stream_camera URL conversion and configuration integration."""

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
