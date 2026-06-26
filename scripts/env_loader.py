"""Shared dotenv loading for Capsule Cinema wrapper scripts."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    _load_dotenv = None


def _load_dotenv_fallback(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_video_agent_env(skill_dir: Path) -> Path | None:
    """Load DOTENV_PATH or the repository-root .env file."""
    if os.environ.get("DOTENV_PATH"):
        candidates = [Path(os.environ["DOTENV_PATH"])]
    else:
        root = Path(skill_dir)
        candidates = [root / ".env", root.parent / ".env"]

    for env_path in candidates:
        env_path = env_path.expanduser()
        if not env_path.exists():
            continue
        if _load_dotenv:
            _load_dotenv(env_path)
        else:
            _load_dotenv_fallback(env_path)
        return env_path
    return None
