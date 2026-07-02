#!/usr/bin/env python3
"""Validate prompt-index style and character consistency."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
LIB_DIR = ROOT / "lib"

sys.path.insert(0, str(LIB_DIR))

from src.visual_consistency_contract import validate_prompt_index, write_json  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"prompt index must be readable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("prompt index root must be an object")
    return payload


def resolve_snapshot_path(index_path: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (index_path.parent / path).resolve(strict=False)


def load_prompt_index_with_snapshots(index_path: Path) -> dict[str, Any]:
    prompt_index = read_json(index_path)
    entries = prompt_index.get("entries") if isinstance(prompt_index.get("entries"), list) else []
    enriched: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        copy = dict(entry)
        raw_path = str(copy.get("path") or "")
        if raw_path and "payload" not in copy:
            snapshot_path = resolve_snapshot_path(index_path, raw_path)
            snapshot = read_json(snapshot_path) if snapshot_path.exists() else {}
            if isinstance(snapshot.get("payload"), dict):
                copy["payload"] = snapshot["payload"]
        enriched.append(copy)
    return {**prompt_index, "entries": enriched, "prompt_index_path": str(index_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-index", required=True, help="Path to prompts/prompt_index.json")
    parser.add_argument("--output", default="", help="Output qa/style_consistency_report.json")
    parser.add_argument("--strict-character-required", action="store_true")
    parser.add_argument("--soft-consistency-ack", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    index_path = Path(args.prompt_index).expanduser().resolve()
    prompt_index = load_prompt_index_with_snapshots(index_path)
    report = validate_prompt_index(
        prompt_index,
        strict_character_required=args.strict_character_required,
        soft_consistency_ack=args.soft_consistency_ack,
    )
    report["prompt_index_path"] = str(index_path)

    if args.output:
        write_json(args.output, report)

    if args.json or not args.output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
