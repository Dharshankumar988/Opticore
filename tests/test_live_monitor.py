"""Tests for LiveEventMonitor event capturing and deduplication."""

from opticore_cli.client import OptiCoreClient
from opticore_cli.live_monitor import LiveEventMonitor
from opticore_cli.voice import VoiceAlertEngine


def test_live_monitor_capture_events(mock_server_url):
    client = OptiCoreClient(base_url=mock_server_url, timeout=3.0)
    voice = VoiceAlertEngine(enabled=False)

    try:
        monitor = LiveEventMonitor(
            client=client,
            voice_engine=voice,
            poll_interval=0.1,
            max_seen_cache=100,
        )

        # Run monitor for a limited number of events (e.g. 2 events)
        captured = monitor.run(max_events=2)
        assert captured >= 2
        assert len(monitor.seen_set) >= 2
    finally:
        voice.shutdown()
