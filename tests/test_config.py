"""Tests for configuration loading, saving, environment variables, and precedence."""

import json
import os
from pathlib import Path
from opticore_cli.config import ConfigManager, OptiCoreConfig


def test_default_config():
    cfg = OptiCoreConfig.defaults()
    assert cfg.server_url == ""
    assert cfg.timeout == 6.0
    assert cfg.poll_interval == 1.0
    assert cfg.voice_enabled is False
    assert cfg.voice_verbosity == "priority"
    assert cfg.voice_rate == 180
    assert cfg.voice_volume == 1.0
    assert cfg.voice_cooldown == 7.0


def test_save_and_load_config(tmp_path: Path):
    cfg_file = tmp_path / "test_config.json"
    mgr = ConfigManager(config_path=cfg_file)

    mgr.set("server_url", "https://opticore-test.ngrok-free.app")
    mgr.set("voice_enabled", True)
    mgr.set("voice_verbosity", "critical")
    mgr.set("voice_rate", 200)
    mgr.save()

    assert cfg_file.is_file()

    # Load again with new manager
    mgr2 = ConfigManager(config_path=cfg_file)
    assert mgr2.config.server_url == "https://opticore-test.ngrok-free.app"
    assert mgr2.config.voice_enabled is True
    assert mgr2.config.voice_verbosity == "critical"
    assert mgr2.config.voice_rate == 200


def test_env_var_override(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "empty_config.json"
    with open(cfg_file, "w") as f:
        json.dump({"server_url": "http://old-url.com"}, f)

    monkeypatch.setenv("OPTICORE_SERVER_URL", "https://override-url.ngrok-free.app")
    monkeypatch.setenv("OPTICORE_VOICE_ENABLED", "true")
    monkeypatch.setenv("OPTICORE_VOICE_VERBOSITY", "all")
    monkeypatch.setenv("OPTICORE_TIMEOUT", "10.5")

    mgr = ConfigManager(config_path=cfg_file)
    assert mgr.config.server_url == "https://override-url.ngrok-free.app"
    assert mgr.config.voice_enabled is True
    assert mgr.config.voice_verbosity == "all"
    assert mgr.config.timeout == 10.5


def test_config_set_type_coercion(tmp_path: Path):
    cfg_file = tmp_path / "coerce_config.json"
    mgr = ConfigManager(config_path=cfg_file)

    # Coerce int
    assert mgr.set("voice_rate", "220")
    assert mgr.config.voice_rate == 220

    # Coerce float
    assert mgr.set("timeout", "8.5")
    assert mgr.config.timeout == 8.5

    # Coerce bool
    assert mgr.set("voice_enabled", "yes")
    assert mgr.config.voice_enabled is True

    # Invalid key
    assert not mgr.set("nonexistent_key", "value")


def test_config_reset(tmp_path: Path):
    cfg_file = tmp_path / "reset_config.json"
    mgr = ConfigManager(config_path=cfg_file)
    mgr.set("voice_rate", 300)
    assert mgr.config.voice_rate == 300

    mgr.reset()
    assert mgr.config.voice_rate == 180
