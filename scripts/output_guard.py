#!/usr/bin/env python3
"""Output path guard for Capsule Cinema scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from src.utils.output_paths import (  # noqa: E402
    OUTPUT_ROOT,
    PROJECT_ROOT,
    get_output_base_dir,
    require_under_output,
    resolve_project_path,
)


OUTPUT_PARAM_KEYS = {
    "output_path",
    "output_dir",
    "save_path",
    "save_dir",
}


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
