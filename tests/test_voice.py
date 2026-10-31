"""Tests for VoiceAlertEngine queuing, verbosity filtering, and deduplication."""

import time
from opticore_cli.models import DetectionEvent
from opticore_cli.voice import VoiceAlertEngine


def make_test_event(name: str, priority: str, message: str) -> DetectionEvent:
    return DetectionEvent(
        timestamp=time.time(),
        track_id=1,
        name=name,
        confidence=0.9,
        class_priority=1,
        position="ahead",
        approaching=True,
        approach_direction="head-on",
        priority=priority,
        risk_score=85.0,
        message=message,
    )


def test_voice_engine_enable_disable():
    engine = VoiceAlertEngine(enabled=False)
    try:
        assert not engine.enabled
        event = make_test_event("car", "P1", "Car approaching.")
        assert not engine.enqueue_event(event)

        engine.set_enabled(True)
        assert engine.enabled
        assert engine.enqueue_event(event)
    finally:
        engine.shutdown()


def test_voice_verbosity_filtering():
    engine = VoiceAlertEngine(enabled=True, verbosity="priority")
    try:
        # P1 Critical class -> should announce
        e1 = make_test_event("car", "P1", "A car appears to be approaching ahead.")
        assert engine.should_announce(e1)

        # P2 person -> should announce under 'priority'
        e2 = make_test_event("person", "P2", "Person detected on your left.")
        assert engine.should_announce(e2)

        # P3 door -> should NOT announce under 'priority'
        e3 = make_test_event("door", "P3", "Door detected ahead.")
        assert not engine.should_announce(e3)

        # Switch to 'all' -> P3 door should now announce
        engine.set_verbosity("all")
        assert engine.should_announce(e3)

        # Switch to 'critical' -> P2 person should NOT announce; only P1 or critical classes
        engine.set_verbosity("critical")
        assert not engine.should_announce(e2)
        assert engine.should_announce(e1)
    finally:
        engine.shutdown()


def test_voice_deduplication_cooldown():
    engine = VoiceAlertEngine(enabled=True, cooldown=5.0)
    try:
        e1 = make_test_event("car", "P1", "Repeated alert message.")
        # First enqueue succeeds
        assert engine.enqueue_event(e1)

        # Immediate identical message fails due to cooldown
        assert not engine.enqueue_event(e1)

        # Different message succeeds immediately
        e2 = make_test_event("bus", "P1", "Different alert message.")
        assert engine.enqueue_event(e2)
    finally:
        engine.shutdown()


def test_voice_status_dict():
    engine = VoiceAlertEngine(enabled=True, verbosity="critical", rate=190, volume=0.8)
    try:
        status = engine.get_status_dict()
        assert status["enabled"] is True
        assert status["verbosity"] == "critical"
        assert status["rate"] == 190
        assert status["volume"] == 0.8
        assert "backend" in status
    finally:
        engine.shutdown()


def test_voice_force_announcement():
    engine = VoiceAlertEngine(enabled=False)
    try:
        # Standard announcement should be rejected when disabled
        e = make_test_event("car", "P1", "Car ahead.")
        assert not engine.enqueue_event(e)
        assert not engine.speak_text("Normal announcement", force=False)

        # Forced announcement should succeed and queue even when voice is disabled
        assert engine.speak_text("Forced test announcement", force=True)
    finally:
        engine.shutdown()

