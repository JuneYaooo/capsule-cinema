"""Load public registries with optional, Git-ignored local overlays.

The public repository contains only approved official integrations and
publishable workflow examples. A developer may keep additional adapters in
``local-channels/`` without adding provider names, endpoints, or credentials to
the Git history.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml


LIB_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = LIB_DIR.parent
PUBLIC_CONFIG_DIR = LIB_DIR / "config"


def local_channels_dir() -> Path:
    configured = os.getenv("CAPSULE_CINEMA_LOCAL_CHANNELS_DIR", "").strip()
    return Path(configured).expanduser() if configured else PROJECT_DIR / "local-channels"


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_registry(filename: str, mapping_key: str) -> dict[str, Any]:
    """Merge a public mapping with an optional local mapping.

    Local records replace public records with the same key. This is deliberate:
    a local checkout may preserve compatibility aliases, while a clean public
    clone sees only the audited official surface.
    """

    public = _read(PUBLIC_CONFIG_DIR / filename)
    merged = dict(public.get(mapping_key) or {})
    local = _read(local_channels_dir() / filename)
    merged.update(local.get(mapping_key) or {})
    return merged


def load_tool_registry() -> dict[str, Any]:
    return load_registry("tool_registry.yaml", "tools")


def load_tool_capabilities() -> dict[str, Any]:
    return load_registry("tool_capabilities.yaml", "tools")
