#!/usr/bin/env python3
"""Build the minimal release manifest for a Capsule Cinema workspace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_FIELDS = [
    "workspace",
    "final_video",
    "cover",
    "storyboard_path",
    "qa_paths",
    "capsule_name",
    "toolchain",
    "created_at",
]


def _path_or_empty(path: Path | None) -> str:
    if path and path.exists():
        return str(path.resolve())
    return ""


def _first_existing(candidates: list[Path]) -> str:
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def _default_qa_paths(workspace: Path) -> list[str]:
    candidates = []
    for directory in [workspace / "release", workspace / "qa", workspace / "work" / "qa"]:
        if directory.is_dir():
            candidates.extend(sorted(directory.glob("*.json")))
    return [str(path.resolve()) for path in candidates]


def build_release_manifest(
    workspace: str | Path,
    *,
    final_video: str | Path | None = None,
    cover: str | Path | None = None,
    storyboard_path: str | Path | None = None,
    qa_paths: list[str | Path] | None = None,
    capsule_name: str = "",
    toolchain: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace).expanduser()
    release_dir = workspace_path / "release"

    manifest = {
        "workspace": str(workspace_path.resolve()),
        "final_video": _path_or_empty(Path(final_video).expanduser()) if final_video else _first_existing([
            release_dir / "final_video.mp4",
            workspace_path / "final" / "final_video.mp4",
        ]),
        "cover": _path_or_empty(Path(cover).expanduser()) if cover else _first_existing([
            release_dir / "cover.png",
            release_dir / "cover.jpg",
            release_dir / "cover.jpeg",
            workspace_path / "cover.png",
        ]),
        "storyboard_path": _path_or_empty(Path(storyboard_path).expanduser()) if storyboard_path else _path_or_empty(
            workspace_path / "storyboard.json"
        ),
        "qa_paths": [str(Path(path).expanduser().resolve()) for path in qa_paths] if qa_paths else _default_qa_paths(
            workspace_path
        ),
        "capsule_name": capsule_name,
        "toolchain": toolchain or {},
        "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return {field: manifest[field] for field in MANIFEST_FIELDS}


def write_release_manifest(
    workspace: str | Path,
    *,
    output_path: str | Path | None = None,
    **kwargs: Any,
) -> Path:
    workspace_path = Path(workspace).expanduser()
    output = Path(output_path).expanduser() if output_path else workspace_path / "release" / "release_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_release_manifest(workspace_path, **kwargs)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Capsule Cinema release manifest")
    parser.add_argument("--workspace", required=True, help="Workspace directory")
    parser.add_argument("--final-video", default=None, help="Final video path")
    parser.add_argument("--cover", default=None, help="Cover image path")
    parser.add_argument("--storyboard-path", default=None, help="Storyboard JSON path")
    parser.add_argument("--qa-path", action="append", default=None, help="QA artifact path; can be repeated")
    parser.add_argument("--capsule-name", default="", help="Capsule name")
    parser.add_argument("--toolchain-json", default="{}", help="JSON object with toolchain metadata")
    parser.add_argument("--created-at", default=None, help="Override created_at timestamp")
    parser.add_argument("--output", default=None, help="Output manifest path")
    args = parser.parse_args()

    try:
        toolchain = json.loads(args.toolchain_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--toolchain-json must be valid JSON: {exc}") from exc
    if not isinstance(toolchain, dict):
        raise SystemExit("--toolchain-json must be a JSON object")

    output = write_release_manifest(
        args.workspace,
        output_path=args.output,
        final_video=args.final_video,
        cover=args.cover,
        storyboard_path=args.storyboard_path,
        qa_paths=args.qa_path,
        capsule_name=args.capsule_name,
        toolchain=toolchain,
        created_at=args.created_at,
    )
    print(output)


if __name__ == "__main__":
    main()
