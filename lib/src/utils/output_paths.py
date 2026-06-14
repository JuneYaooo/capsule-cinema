from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "output"


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
