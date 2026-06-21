from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from src.utils.output_paths import OUTPUT_ROOT


def default_video_output_dir(engine: str) -> str:
    return str(OUTPUT_ROOT / "manual_tool" / "work" / "videos" / engine)


def resolve_video_output_dir(
    output_dir: Optional[str],
    output_path: Optional[str],
    default_output_dir: str,
    legacy_output_dirs: Iterable[str] = (),
) -> str:
    selected = output_dir or default_output_dir
    if _matches_default_dir(selected, default_output_dir, legacy_output_dirs):
        if output_path:
            return str(Path(output_path).expanduser().parent)
        return default_output_dir
    return selected


def _matches_default_dir(
    value: str,
    default_output_dir: str,
    legacy_output_dirs: Iterable[str],
) -> bool:
    raw_value = _clean_dir_text(value)
    raw_defaults = {_clean_dir_text(default_output_dir)}
    raw_defaults.update(_clean_dir_text(item) for item in legacy_output_dirs)
    if raw_value in raw_defaults:
        return True

    try:
        return Path(value).expanduser().resolve(strict=False) == Path(default_output_dir).expanduser().resolve(strict=False)
    except OSError:
        return False


def _clean_dir_text(value: str) -> str:
    return str(value).strip().rstrip("/")
