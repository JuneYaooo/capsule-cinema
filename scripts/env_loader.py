"""Shared dotenv loading for Capsule Cinema wrapper scripts."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_video_agent_env(skill_dir: Path) -> Path | None:
    """Load DOTENV_PATH or the repository-root .env file."""
    env_path = Path(os.environ.get("DOTENV_PATH") or skill_dir.parent / ".env")
    if env_path.exists():
        load_dotenv(env_path)
        return env_path
    return None
