#!/usr/bin/env python3
"""Build a release checkpoint from a Capsule Cinema workspace."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "lib"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from output_guard import require_under_output, require_workspace_under_output  # noqa: E402


REMOTE_OR_SECRET_PATTERN = re.compile(
    r"(https?://|s3://|oss://|qiniu://|bearer\s+[A-Za-z0-9._-]+|sk-[A-Za-z0-9_-]{20,}|"
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|secret)(?:[\"']?\s*[:=]\s*|=)[\"']?[A-Za-z0-9._~+/=-]{8,})",
    re.I,
)


def read_json(path: Path | None, fallback: Any) -> Any:
    if not path or not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def artifact_path(manifest: dict[str, Any], category: str) -> str:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    for item in artifacts:
        if isinstance(item, dict) and item.get("category") == category and item.get("path"):
            return str(item["path"])
    return ""


def artifact_exists(manifest: dict[str, Any], category: str) -> bool:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    return any(isinstance(item, dict) and item.get("category") == category for item in artifacts)


def load_delivery_promise(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    promise = manifest.get("delivery_promise")
    if isinstance(promise, dict):
        return promise
    proposal = read_json(workspace / "work" / "production_proposal.json", {})
    promise = proposal.get("delivery_promise") if isinstance(proposal, dict) else None
    if isinstance(promise, dict):
        return promise
    storyboard = read_json(workspace / "storyboard.json", {})
    promise = storyboard.get("delivery_promise") if isinstance(storyboard, dict) else None
    return promise if isinstance(promise, dict) else {}


def _source_review_exists(workspace: Path, manifest: dict[str, Any]) -> bool:
    if artifact_exists(manifest, "source_media_review"):
        return True
    candidates = [
        workspace / "work" / "source_media_review.json",
        workspace / "qa" / "source_media_review.json",
    ]
    return any(path.exists() for path in candidates)


def _reference_analysis_exists(workspace: Path, manifest: dict[str, Any]) -> bool:
    if artifact_exists(manifest, "reference_analysis") or artifact_exists(manifest, "video_analysis_brief"):
        return True
    candidates = [
        workspace / "work" / "reference_analysis.json",
        workspace / "work" / "video_analysis_brief.json",
        workspace / "qa" / "reference_analysis.json",
    ]
    return any(path.exists() for path in candidates)


def _decision_log_exists(workspace: Path, manifest: dict[str, Any]) -> bool:
    if artifact_exists(manifest, "decision_log"):
        return True
    return (workspace / "work" / "decision_log.json").exists()


def _has_specialized_output(workspace: Path, manifest: dict[str, Any]) -> bool:
    specialized_categories = {
        "action_animation_video",
        "action_transfer_video",
        "code_rendered_video",
        "lip_sync_video",
        "digital_human_video",
        "music_mv_video",
        "super_resolution_video",
        "specialized_output",
    }
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    if any(isinstance(item, dict) and item.get("category") in specialized_categories for item in artifacts):
        return True
    specialized_dirs = [
        workspace / "work" / "temp" / "action_animation",
        workspace / "work" / "temp" / "action_transfer",
        workspace / "work" / "temp" / "code_rendered",
        workspace / "work" / "temp" / "lipsync",
        workspace / "work" / "temp" / "music_mv",
        workspace / "work" / "temp" / "super_resolution",
    ]
    return any(path.exists() and any(path.rglob("*.mp4")) for path in specialized_dirs)


def evaluate_delivery_promise(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Return promise preservation status for release gating."""
    promise = load_delivery_promise(workspace, manifest)
    promise_type = str(promise.get("promise_type") or "")
    if not promise_type:
        return {
            "promise": {},
            "ok": True,
            "blockers": [],
            "warnings": ["delivery_promise_missing"],
        }

    approved_fallback = str(promise.get("approved_fallback") or "")
    blockers: list[str] = []
    warnings: list[str] = []

    if promise_type == "source_led" and not _source_review_exists(workspace, manifest):
        blockers.append("delivery_promise:source_led_missing_source_review")
    if promise_type == "reference_remake" and not _reference_analysis_exists(workspace, manifest):
        blockers.append("delivery_promise:reference_remake_missing_reference_analysis")
    if promise_type == "specialized_route":
        if not _has_specialized_output(workspace, manifest) and approved_fallback != "generic_preview":
            blockers.append("delivery_promise:specialized_route_requires_specialized_output")
    if promise_type in {"motion_led", "specialized_route", "source_led", "reference_remake"}:
        if not _decision_log_exists(workspace, manifest):
            warnings.append("decision_log_missing_for_promise_sensitive_run")

    return {
        "promise": promise,
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def resolve_existing_path(workspace: Path, value: str) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve(strict=False) if path.exists() else None


def collect_artifact(workspace: Path, category: str, path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    return {
        "category": category,
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
    }


def build_release_checkpoint(
    workspace: str | Path,
    *,
    manifest_path: str | Path | None = None,
    edit_plan_path: str | Path | None = None,
    edit_plan_validation_path: str | Path | None = None,
    quality_score_path: str | Path | None = None,
    repair_plan_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace_path = require_workspace_under_output(workspace)
    manifest_file = Path(manifest_path).expanduser() if manifest_path else workspace_path / "artifact_manifest.json"
    if not manifest_file.is_absolute():
        manifest_file = workspace_path / manifest_file
    manifest = read_json(manifest_file, {})

    edit_plan_file = Path(edit_plan_path).expanduser() if edit_plan_path else workspace_path / "work" / "edit_plan.json"
    edit_plan_validation_file = (
        Path(edit_plan_validation_path).expanduser()
        if edit_plan_validation_path
        else workspace_path / "qa" / "edit_plan_validation.json"
    )
    quality_file = Path(quality_score_path).expanduser() if quality_score_path else workspace_path / "qa" / "video_quality_score.json"
    local_qa_file = workspace_path / "qa" / "local_video_qa.json"
    repair_file = Path(repair_plan_path).expanduser() if repair_plan_path else workspace_path / "qa" / "repair_plan.json"
    storyboard_file = first_existing([workspace_path / "storyboard.json"])
    final_video = resolve_existing_path(workspace_path, artifact_path(manifest, "final_video")) or first_existing(
        sorted((workspace_path / "release").glob("*.mp4"))
        + sorted((workspace_path / "final").glob("*.mp4"))
    )
    cover = resolve_existing_path(workspace_path, artifact_path(manifest, "cover_image")) or first_existing(
        sorted((workspace_path / "release").glob("cover.*"))
    )
    copywriting = resolve_existing_path(workspace_path, artifact_path(manifest, "copywriting"))
    contact_sheet = first_existing([workspace_path / "qa" / "review_contact_sheet.jpg"])
    multimodal_review = first_existing([workspace_path / "qa" / "multimodal_video_review.json"])

    quality = read_json(quality_file, {})
    edit_plan_validation = read_json(edit_plan_validation_file, {})
    local_qa = read_json(local_qa_file, {})
    repair_plan = read_json(repair_file, {})
    blockers = quality.get("blockers") if isinstance(quality.get("blockers"), list) else []
    warnings = quality.get("warnings") if isinstance(quality.get("warnings"), list) else []
    edit_plan_blockers = (
        edit_plan_validation.get("blockers")
        if isinstance(edit_plan_validation.get("blockers"), list)
        else []
    )
    promise_review = evaluate_delivery_promise(workspace_path, manifest)
    promise_blockers = promise_review["blockers"]
    promise_warnings = promise_review["warnings"]
    quality_status = str(quality.get("status") or "")

    checks = [
        {
            "id": "final_video_exists",
            "ok": bool(final_video),
            "severity": "blocker",
            "detail": str(final_video or ""),
        },
        {
            "id": "artifact_manifest_exists",
            "ok": bool(manifest),
            "severity": "blocker",
            "detail": str(manifest_file),
        },
        {
            "id": "edit_plan_exists",
            "ok": edit_plan_file.exists(),
            "severity": "warning",
            "detail": str(edit_plan_file),
        },
        {
            "id": "edit_plan_validated",
            "ok": bool(edit_plan_validation.get("ok")) if edit_plan_validation else False,
            "severity": "warning",
            "detail": str(edit_plan_validation_file),
        },
        {
            "id": "quality_score_available",
            "ok": bool(quality),
            "severity": "warning",
            "detail": str(quality_file),
        },
        {
            "id": "local_qa_passed",
            "ok": bool(local_qa.get("ok")) if local_qa else False,
            "severity": "warning",
            "detail": str(local_qa_file),
        },
        {
            "id": "repair_plan_clear",
            "ok": not bool(repair_plan.get("blocking")),
            "severity": "warning",
            "detail": str(repair_file) if repair_file.exists() else "not generated",
        },
        {
            "id": "delivery_promise_honored",
            "ok": bool(promise_review["ok"]),
            "severity": "blocker",
            "detail": ",".join(promise_blockers) if promise_blockers else promise_review["promise"].get("promise_type", ""),
        },
    ]

    payload_for_secret_scan = json.dumps(
        {
            "manifest": manifest,
            "quality": quality,
            "edit_plan_validation": edit_plan_validation,
            "repair_plan": repair_plan,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    checks.append(
        {
            "id": "no_remote_or_secret_paths",
            "ok": REMOTE_OR_SECRET_PATTERN.search(payload_for_secret_scan) is None,
            "severity": "blocker",
            "detail": "manifest/QA/edit plan validation/repair plan path scan",
        }
    )

    hard_failures = [item for item in checks if not item["ok"] and item["severity"] == "blocker"]
    if blockers or edit_plan_blockers or promise_blockers or hard_failures or quality_status == "fail":
        status = "blocked"
    elif quality_status in {"pass", "needs_review"}:
        status = quality_status
    elif final_video:
        status = "needs_review"
    else:
        status = "blocked"

    artifacts = [
        collect_artifact(workspace_path, "final_video", final_video),
        collect_artifact(workspace_path, "cover_image", cover),
        collect_artifact(workspace_path, "copywriting", copywriting),
        collect_artifact(workspace_path, "storyboard", storyboard_file),
        collect_artifact(workspace_path, "edit_plan", edit_plan_file),
        collect_artifact(workspace_path, "edit_plan_validation", edit_plan_validation_file),
        collect_artifact(workspace_path, "quality_score", quality_file),
        collect_artifact(workspace_path, "local_video_qa", local_qa_file),
        collect_artifact(workspace_path, "repair_plan", repair_file),
        collect_artifact(workspace_path, "contact_sheet", contact_sheet),
        collect_artifact(workspace_path, "multimodal_review", multimodal_review),
        collect_artifact(workspace_path, "decision_log", workspace_path / "work" / "decision_log.json"),
        collect_artifact(workspace_path, "production_proposal", workspace_path / "work" / "production_proposal.json"),
    ]

    return {
        "schema": "capsule_cinema.release_checkpoint.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workspace": str(workspace_path),
        "status": status,
        "release_ready": status == "pass" and not blockers and not edit_plan_blockers and not promise_blockers and not hard_failures,
        "delivery_promise": promise_review["promise"],
        "quality_status": quality_status,
        "edit_plan_validation_status": edit_plan_validation.get("status") if edit_plan_validation else "",
        "score": quality.get("score"),
        "score_max": quality.get("score_max"),
        "blockers": blockers + edit_plan_blockers + promise_blockers,
        "warnings": warnings + promise_warnings,
        "checks": checks,
        "artifacts": [item for item in artifacts if item],
    }


def write_release_checkpoint(
    workspace: str | Path,
    *,
    output_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    edit_plan_path: str | Path | None = None,
    edit_plan_validation_path: str | Path | None = None,
    quality_score_path: str | Path | None = None,
    repair_plan_path: str | Path | None = None,
) -> Path:
    workspace_path = require_workspace_under_output(workspace)
    output = require_under_output(output_path, "--output") if output_path else workspace_path / "release" / "release_checkpoint.json"
    checkpoint = build_release_checkpoint(
        workspace_path,
        manifest_path=manifest_path,
        edit_plan_path=edit_plan_path,
        edit_plan_validation_path=edit_plan_validation_path,
        quality_score_path=quality_score_path,
        repair_plan_path=repair_plan_path,
    )
    write_json(output, checkpoint)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "--run-dir", dest="workspace", required=True, help="Workspace under output/")
    parser.add_argument("--manifest", default="", help="Optional artifact manifest path")
    parser.add_argument("--edit-plan", default="", help="Optional edit_plan.json path")
    parser.add_argument("--edit-plan-validation", default="", help="Optional edit_plan_validation.json path")
    parser.add_argument("--quality-score", default="", help="Optional video_quality_score.json path")
    parser.add_argument("--repair-plan", default="", help="Optional repair_plan.json path")
    parser.add_argument("--output", default="", help="Output release_checkpoint.json path under output/")
    parser.add_argument("--json", action="store_true", help="Print checkpoint JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        workspace = require_workspace_under_output(args.workspace)
        output = write_release_checkpoint(
            workspace,
            output_path=args.output or None,
            manifest_path=args.manifest or None,
            edit_plan_path=args.edit_plan or None,
            edit_plan_validation_path=args.edit_plan_validation or None,
            quality_score_path=args.quality_score or None,
            repair_plan_path=args.repair_plan or None,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if args.json:
        print(json.dumps(read_json(output, {}), ensure_ascii=False, indent=2))
    else:
        print(output)


if __name__ == "__main__":
    main()
