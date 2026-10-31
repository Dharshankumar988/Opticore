"""Tests for InteractiveMenu toggle actions, navigation, and window launching."""

import pytest
from opticore_cli.cli import OptiCoreCLI
from opticore_cli.config import ConfigManager
from opticore_cli.menu import (
    InteractiveMenu,
    launch_camera_in_new_window,
    launch_in_new_window,
)


@pytest.fixture
def test_menu(tmp_path):
    cfg_file = tmp_path / "menu_test_config.json"
    mgr = ConfigManager(config_path=cfg_file)
    cli = OptiCoreCLI(config_manager=mgr)
    menu = InteractiveMenu(cli)
    yield menu
    cli.shutdown()


def test_menu_items_structure(test_menu):
    items = test_menu.get_menu_items()
    assert isinstance(items, list)
    assert len(items) >= 14

    ids = [item["id"] for item in items]
    assert "connect" in ids
    assert "camera_toggle" in ids
    assert "camera_stream_new" in ids
    assert "camera_source_toggle" in ids
    assert "camera_preview_toggle" in ids
    assert "monitor_new" in ids
    assert "voice_toggle" in ids
    assert "voice_verb" in ids
    assert "status" in ids
    assert "health" in ids
    assert "exit" in ids


def test_menu_voice_toggle_action(test_menu):
    # Initially False
    test_menu.cli.voice.set_enabled(False)
    assert not test_menu.cli.voice.enabled

    # Toggle to True
    items = test_menu.get_menu_items()
    toggle_item = next(it for it in items if it["id"] == "voice_toggle")
    assert "OFF" in toggle_item["label"]

    test_menu.cli.voice.set_enabled(True)
    items_after = test_menu.get_menu_items()
    toggle_item_after = next(it for it in items_after if it["id"] == "voice_toggle")
    assert "ON" in toggle_item_after["label"]


def test_menu_camera_toggle_actions(test_menu):
    # Camera preview toggle
    test_menu.cli.config.camera_show_preview = False
    items = test_menu.get_menu_items()
    preview_item = next(it for it in items if it["id"] == "camera_preview_toggle")
    assert "OFF" in preview_item["label"]

    test_menu.cli.config.camera_show_preview = True
    items_after = test_menu.get_menu_items()
    preview_item_after = next(it for it in items_after if it["id"] == "camera_preview_toggle")
    assert "ON" in preview_item_after["label"]

    # Camera source label check
    test_menu.cli.config.camera_source = "0"
    items_source = test_menu.get_menu_items()
    src_item = next(it for it in items_source if it["id"] == "camera_source_toggle")
    assert "Device 0" in src_item["label"]


def test_menu_cycle_verbosity(test_menu):
    test_menu.cli.voice.set_verbosity("priority")
    assert test_menu.cli.voice.verbosity == "priority"

    # Simulate cycling verbosity
    levels = ["priority", "critical", "all"]
    for expected in ["critical", "all", "priority"]:
        curr = test_menu.cli.voice.verbosity
        next_v = levels[(levels.index(curr) + 1) % len(levels)]
        test_menu.cli.voice.set_verbosity(next_v)
        assert test_menu.cli.voice.verbosity == expected


def test_launch_in_new_window_mocked(monkeypatch):
    launched_args = []

    def mock_popen(args, **kwargs):
        launched_args.append((args, kwargs))
        class MockProcess:
            pid = 9999
        return MockProcess()

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    ok, msg = launch_in_new_window(server_url="http://127.0.0.1:8000", poll=0.5, voice=True, verbosity="critical")
    assert ok is True
    assert len(launched_args) == 1
    args, kwargs = launched_args[0]
    assert any("monitor" in str(arg) for arg in args)


def test_launch_camera_in_new_window_mocked(monkeypatch):
    launched_args = []

    def mock_popen(args, **kwargs):
        launched_args.append((args, kwargs))
        class MockProcess:
            pid = 8888
        return MockProcess()

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    ok, msg = launch_camera_in_new_window(
        server_url="https://test.ngrok-free.app",
        camera_source="0",
        fps=15.0,
        width=640,
        quality=65,
        show_window=True,
    )
    assert ok is True
    assert len(launched_args) == 1
    args, kwargs = launched_args[0]
    assert any("camera" in str(arg) for arg in args)
