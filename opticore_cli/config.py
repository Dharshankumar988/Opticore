"""Configuration management for OptiCore CLI Command Center.

Supports loading from JSON files, environment variables, and CLI overrides.
Precedence: CLI Arguments > Environment Variables > Config File > Defaults.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# Default configuration file locations
DEFAULT_GLOBAL_CONFIG_PATH = Path.home() / ".opticore" / "config.json"
LOCAL_CONFIG_PATH = Path("opticore.config.json")


@dataclass
class OptiCoreConfig:
    server_url: str = ""
    timeout: float = 6.0
    poll_interval: float = 1.0
    voice_enabled: bool = False
    voice_verbosity: str = "priority"  # "all", "priority", "critical"
    voice_rate: int = 180
    voice_volume: float = 1.0
    voice_cooldown: float = 7.0
    max_log_history: int = 500

    @classmethod
    def defaults(cls) -> "OptiCoreConfig":
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptiCoreConfig":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class ConfigManager:
    """Manages loading, updating, and persisting OptiCore configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._discover_config_path()
        self.config = self.load()

    def _discover_config_path(self) -> Path:
        """Prefers local config file if exists; otherwise defaults to user home."""
        if LOCAL_CONFIG_PATH.is_file():
            return LOCAL_CONFIG_PATH
        return DEFAULT_GLOBAL_CONFIG_PATH

    def load(self) -> OptiCoreConfig:
        """Loads configuration combining file defaults, env vars, and defaults."""
        data = OptiCoreConfig.defaults().to_dict()

        # 1. Read from file if present
        if self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    if isinstance(file_data, dict):
                        data.update(file_data)
            except Exception:
                # If config file is corrupted or unreadable, fall back to defaults
                pass

        # 2. Apply Environment Variables
        if "OPTICORE_SERVER_URL" in os.environ:
            data["server_url"] = os.environ["OPTICORE_SERVER_URL"].strip()

        if "OPTICORE_TIMEOUT" in os.environ:
            try:
                data["timeout"] = float(os.environ["OPTICORE_TIMEOUT"])
            except ValueError:
                pass

        if "OPTICORE_POLL_INTERVAL" in os.environ:
            try:
                data["poll_interval"] = float(os.environ["OPTICORE_POLL_INTERVAL"])
            except ValueError:
                pass

        if "OPTICORE_VOICE_ENABLED" in os.environ:
            val = os.environ["OPTICORE_VOICE_ENABLED"].strip().lower()
            data["voice_enabled"] = val in {"1", "true", "yes", "on"}

        if "OPTICORE_VOICE_VERBOSITY" in os.environ:
            verb = os.environ["OPTICORE_VOICE_VERBOSITY"].strip().lower()
            if verb in {"all", "priority", "critical"}:
                data["voice_verbosity"] = verb

        if "OPTICORE_VOICE_RATE" in os.environ:
            try:
                data["voice_rate"] = int(os.environ["OPTICORE_VOICE_RATE"])
            except ValueError:
                pass

        if "OPTICORE_VOICE_VOLUME" in os.environ:
            try:
                vol = float(os.environ["OPTICORE_VOICE_VOLUME"])
                data["voice_volume"] = max(0.0, min(1.0, vol))
            except ValueError:
                pass

        if "OPTICORE_VOICE_COOLDOWN" in os.environ:
            try:
                data["voice_cooldown"] = float(os.environ["OPTICORE_VOICE_COOLDOWN"])
            except ValueError:
                pass

        self.config = OptiCoreConfig.from_dict(data)
        return self.config

    def save(self, path: Optional[Path] = None) -> Path:
        """Saves current config to disk."""
        target = path or self.config_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=2)
        return target

    def set(self, key: str, value: Any) -> bool:
        """Sets a configuration key with type coercion."""
        if not hasattr(self.config, key):
            return False

        current_val = getattr(self.config, key)
        try:
            if isinstance(current_val, bool):
                if isinstance(value, str):
                    coerced = value.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    coerced = bool(value)
            elif isinstance(current_val, int):
                coerced = int(value)
            elif isinstance(current_val, float):
                coerced = float(value)
            else:
                coerced = str(value)
            setattr(self.config, key, coerced)
            return True
        except (ValueError, TypeError):
            return False

    def reset(self) -> None:
        """Resets config to defaults and saves."""
        self.config = OptiCoreConfig.defaults()
        self.save()
