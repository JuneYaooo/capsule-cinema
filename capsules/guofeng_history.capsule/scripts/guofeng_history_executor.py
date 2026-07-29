#!/usr/bin/env python3.12
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lib"))

from video_workflows.exact_paid_capsules import (  # noqa: E402
    ExactCapsuleError,
    _locked_storyboard,
    execute_guofeng_history,
    preflight_exact_paid_capsules,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    params = json.loads(Path(args.params).read_text(encoding="utf-8"))
    try:
        preflight = preflight_exact_paid_capsules()
        storyboard_path, _, scenes = _locked_storyboard(params, output, expected_scenes=10)
        durations = [float(scene["duration"]) for scene in scenes]
        if abs(sum(durations) - 55.0) > 0.05:
            raise ExactCapsuleError("guofeng_history scene durations must sum to 55 seconds")
        if args.dry_run:
            report = {"ok": True, "dry_run": True, "provider_calls": 0, "storyboard_path": str(storyboard_path), "preflight": preflight["guofeng_history"]}
            path = output / "reports" / "run_notes.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (output / "artifact_manifest.json").write_text(json.dumps({"dry_run": True, "deliverable": False, "artifacts": [{"path": str(path), "category": "qa", "title": "Guofeng exact-route preflight"}]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False))
            return 0
        result = execute_guofeng_history(args.topic, params, output)
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except ExactCapsuleError as exc:
        report = {"ok": False, "success": False, "deliverable": False, "run_status": "generation_failed", "error": str(exc)}
        path = output / "reports" / "run_notes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
