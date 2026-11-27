"""Portable paths and explicit modern configuration precedence."""

import json
import os
import sys
from pathlib import Path

from .contracts import Problem

ENV = {"google_api_key": "GOOGLE_API_KEY", "google_cx": "GOOGLE_CX",
       "brave_api_key": "BRAVE_API_KEY", "serper_api_key": "SERPER_API_KEY",
       "yandex_user": "YANDEX_USER", "yandex_key": "YANDEX_KEY",
       "mojeek_api_key": "MOJEEK_API_KEY", "searxng_url": "SEARXNG_URL",
       "proxy": "AVAILGATE_PROXY", "ghdb_path": "GHDB_PATH"}


def paths():
    home = Path.home()
    if sys.platform == "win32":
        config = Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / "AvailGate"
        data = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "AvailGate"
    elif sys.platform == "darwin":
        config = data = home / "Library/Application Support/AvailGate"
    else:
        config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "availgate"
        data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "availgate"
    return (Path(os.environ.get("AVAILGATE_CONFIG", config / "config.json")).expanduser(),
            Path(os.environ.get("AVAILGATE_DATA_DIR", data)).expanduser())


def load(overrides=None):
    path, _ = paths()
    warnings = []
    legacy = Path.home() / ".availgate.json"
    if not path.exists() and "AVAILGATE_CONFIG" not in os.environ and legacy.exists():
        path = legacy
        warnings.append("Using legacy configuration with modern precedence: environment overrides file values.")
    config = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError()
            for key in ENV:
                if key in config and not isinstance(config[key], str):
                    raise ValueError()
        except (ValueError, OSError):
            raise Problem("configuration", "Configuration must be a readable JSON object with string provider settings.", invalid=True)
    elif "AVAILGATE_CONFIG" in os.environ:
        raise Problem("configuration", "Explicit configuration file does not exist.", invalid=True)
    config.update({key: os.environ[name] for key, name in ENV.items() if name in os.environ})
    config.update({key: value for key, value in (overrides or {}).items() if value is not None})
    return config, warnings
