#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from src.capsule_gate_runner import run_capsule_gates  # noqa: E402


def _read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.exists():
        raise SystemExit(f"payload not found: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("payload must be a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run executable capsule gate bindings.")
    parser.add_argument("--capsule-dir", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--payload", default="", help="JSON object with profile, manifest, and/or release keys.")
    parser.add_argument("--profile", default="", help="Profile JSON path.")
    parser.add_argument("--manifest", default="", help="Manifest JSON path.")
    parser.add_argument("--release", default="", help="Release JSON path.")
    parser.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = _read_json(args.payload) if args.payload else {}
    profile = _read_json(args.profile) if args.profile else payload.get("profile")
    manifest = _read_json(args.manifest) if args.manifest else payload.get("manifest")
    release = _read_json(args.release) if args.release else payload.get("release")
    report = run_capsule_gates(
        args.capsule_dir,
        args.phase,
        profile=profile if isinstance(profile, dict) else None,
        manifest=manifest if isinstance(manifest, dict) else None,
        release=release if isinstance(release, dict) else None,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
