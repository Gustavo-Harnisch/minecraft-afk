"""Persistencia sencilla de la configuración de la interfaz."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "mob_farm": {
        "interval": 2.0,
    },
    "stone_farm": {
        "pickaxe": "diamond",
        "current_durability": 1561,
        "minimum_durability": 100,
        "efficiency": 0,
        "unbreaking": 0,
        "haste": 0,
        "calculation_method": "calibrated",
        "calibrated_seconds_per_durability": 1.474,
        "calibration_mode": False,
        "calibration_before": 962,
        "calibration_after": 943,
        "calibration_seconds": 30.0,
        "auto_stop": True,
    },
}


def _merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.path = path or config_home / "minecraft-afk" / "config.json"
        self.data = deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> dict[str, Any]:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = _merge(DEFAULT_SETTINGS, loaded)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.data = deepcopy(DEFAULT_SETTINGS)
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
