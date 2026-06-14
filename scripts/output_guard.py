#!/usr/bin/env python3
"""Output path guard for Capsule Cinema scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "output"
OUTPUT_PARAM_KEYS = {
    "output_path",
    "output_dir",
    "save_path",
    "save_dir",
}


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve(strict=False)


def require_under_output(value: str | Path, label: str = "output path") -> Path:
    path = resolve_project_path(value)
    root = OUTPUT_ROOT.resolve(strict=False)
    if path != root and not path.is_relative_to(root):
        raise ValueError(f"{label} must be under {root}: {path}")
    return path


def get_output_base_dir(override: Optional[str] = None) -> Path:
    candidate = override or os.environ.get("OPENCLAW_OUTPUT_DIR") or OUTPUT_ROOT
    base = require_under_output(candidate, "OPENCLAW_OUTPUT_DIR")
    base.mkdir(parents=True, exist_ok=True)
    return base


def require_workspace_under_output(value: str | Path) -> Path:
    return require_under_output(value, "workspace_dir")


def normalize_output_params(value: Any, label: str = "params") -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            child_label = f"{label}.{key}"
            if key in OUTPUT_PARAM_KEYS and isinstance(item, str) and item.strip():
                normalized[key] = str(require_under_output(item, child_label))
            else:
                normalized[key] = normalize_output_params(item, child_label)
        return normalized
    if isinstance(value, list):
        return [normalize_output_params(item, f"{label}[]") for item in value]
    return value
