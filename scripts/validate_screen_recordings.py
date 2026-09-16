#!/usr/bin/env python3
"""Validate real GitHub/WorkBuddy recording provenance for the recording capsule."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def validate(manifest_path: Path) -> tuple[bool, list[str]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"cannot read manifest: {exc}"]
    errors: list[str] = []
    if manifest.get("schema") != "capsule_cinema.screen_recording_manifest.v1":
        errors.append("schema must be capsule_cinema.screen_recording_manifest.v1")
    mode = str(manifest.get("screen_recording_mode") or "").strip()
    if mode not in {"github_only", "workbuddy_only", "github_and_workbuddy"}:
        errors.append("screen_recording_mode must be github_only, workbuddy_only, or github_and_workbuddy")
    recordings = manifest.get("recordings")
    if not isinstance(recordings, list):
        return False, errors + ["recordings must be a list"]
    by_kind: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(recordings):
        if not isinstance(item, dict):
            errors.append(f"recordings[{index}] must be an object")
            continue
        kind = str(item.get("kind") or "").strip()
        by_kind[kind] = item
        path_text = str(item.get("path") or item.get("raw_path") or "").strip()
        if not path_text:
            errors.append(f"recordings[{index}] missing path/raw_path")
            continue
        path = Path(path_text).expanduser()
        if not path.is_file():
            errors.append(f"recordings[{index}] media missing: {path}")
            continue
        actual_sha = _sha256(path)
        if str(item.get("sha256") or "") != actual_sha:
            errors.append(f"recordings[{index}] sha256 mismatch for {path}")
        try:
            duration = _duration(path)
            if not 2.0 <= duration <= 6.0:
                errors.append(f"recordings[{index}] duration {duration:.2f}s must be between 2 and 6 seconds")
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            errors.append(f"recordings[{index}] ffprobe failed: {exc}")
        for key in ("captured_at", "timeline_start_seconds", "timeline_end_seconds"):
            if key not in item or item[key] in (None, ""):
                errors.append(f"recordings[{index}] missing {key}")

        if kind == "github":
            required = {
                "capture_method": "actual_browser_github_scroll_recording",
                "source_url": manifest.get("project_url"),
            }
            for key, expected in required.items():
                if item.get(key) != expected:
                    errors.append(f"GitHub recording {key} must be {expected!r}")
            if not isinstance(item.get("viewport"), list) or len(item["viewport"]) != 2:
                errors.append("GitHub recording viewport must be [width, height]")
            if item.get("privacy_review") != "passed":
                errors.append("GitHub recording privacy_review must be passed")
        elif kind == "workbuddy":
            if item.get("capture_method") != "native_obs_workbuddy_window_recording":
                errors.append("WorkBuddy recording capture_method must be native_obs_workbuddy_window_recording")
            for key, expected in {
                "window_capture": True,
                "history_sidebar": "collapsed",
                "artifact_panel": "visible",
                "privacy_review": "passed",
            }.items():
                if item.get(key) != expected:
                    errors.append(f"WorkBuddy recording {key} must be {expected!r}")
            edited = str(item.get("edited_path") or "").strip()
            if edited and not Path(edited).expanduser().is_file():
                errors.append(f"WorkBuddy edited_path missing: {edited}")
    if mode in {"github_only", "github_and_workbuddy"} and "github" not in by_kind:
        errors.append("selected mode requires a GitHub recording")
    if mode in {"workbuddy_only", "github_and_workbuddy"} and "workbuddy" not in by_kind:
        errors.append("selected mode requires a WorkBuddy recording")
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    ok, errors = validate(args.manifest.expanduser().resolve())
    print(json.dumps({"ok": ok, "manifest": str(args.manifest.resolve()), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
