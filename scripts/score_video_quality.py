#!/usr/bin/env python3
"""Score a generated video against local QA, capsule contract, and common issue gates."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "lib"
RUBRIC_PATH = LIB_DIR / "config" / "video_quality_rubric.json"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from capsule_runtime import load_capsule, capsule_requires_special_route  # noqa: E402
from local_video_qa import run_qa as run_local_video_qa  # noqa: E402
from output_guard import OUTPUT_ROOT, require_under_output, require_workspace_under_output  # noqa: E402


REMOTE_OR_SECRET_PATTERN = re.compile(
    r"(https?://|s3://|oss://|qiniu://|bearer\s+[A-Za-z0-9._-]+|sk-[A-Za-z0-9_-]{20,}|"
    r"api[_-]?key|access[_-]?token|authorization|cookie|secret)",
    re.I,
)
SPEECH_SYNC_KEYWORDS = (
    "digital_human",
    "presenter",
    "lipsync",
    "lip_sync",
    "speech_sync",
    "talking_head",
    "avatar",
    "口播",
    "同步路线",
)
TEXT_LAYOUT_KEYWORDS = (
    "subtitle",
    "caption",
    "lower-third",
    "title card",
    "data card",
    "字幕",
    "标题",
    "角标",
    "卡片",
    "文字",
    "文案",
    "换行",
)
VOICE_CHARACTER_KEYWORDS = (
    "presenter",
    "talking head",
    "avatar",
    "host",
    "woman",
    "man",
    "girl",
    "boy",
    "female",
    "male",
    "主播",
    "主持",
    "口播",
    "真人",
    "人物",
    "女性",
    "男性",
    "女生",
    "男生",
    "女孩",
    "男孩",
    "虚拟人",
)

MULTIMODAL_REVIEW_PROMPT = """你是短视频成片质检员。请逐段观看这个视频，并按严格 JSON 返回审核结果。

重点检查:
1. 口播/同步类问题: 声音、口型、表情、手势和身体节奏是否明显错位。
2. 卡顿冻结: 是否出现有声音但人物脸/嘴/身体卡住、停住、循环抖动或长时间静帧。
3. 音画节奏: 旁白继续时画面是否明显跟不上、突然跳帧、动作和字幕节奏脱节。
4. 主体质量: 主角脸、手、身体、宠物或食物是否严重变形。
5. 字幕/画面文字: 字幕或画面字体是否溢出、被裁切、太小、比例不协调、换行不自然、出现乱码/异常字符/孤立标点。
6. 角色和声线: 画面人物的性别/年龄感/角色定位与配音声线是否明显不匹配，例如画面是女生但配音是明显男声，或儿童形象配成年男性声线。
7. 画面异常: 黑屏、白屏、乱码文字、水印、严重闪烁、主体被错误裁切。

请只把普通观众一眼能感知的问题列为 blocker。轻微不完美可列为 warning。
如果你不能可靠听到或理解音频，也要明确说明，不能假装已经确认同步。

必须返回 JSON，格式如下:
{
  "success": true,
  "has_issues": true,
  "needs_regeneration": true,
  "quality_score": 1,
  "speech_visual_sync": {
    "ok": true,
    "severity": "pass|warning|blocker|unknown",
    "evidence": "口型/表情/手势与声音是否同步的简短证据",
    "timestamps": ["00:03"]
  },
  "motion_continuity": {
    "ok": true,
    "severity": "pass|warning|blocker|unknown",
    "evidence": "是否有声音继续但画面卡住/嘴不动/动作循环的简短证据",
    "timestamps": []
  },
  "subtitle_text_layout": {
    "ok": true,
    "severity": "pass|warning|blocker|unknown",
    "evidence": "字幕/画面文字是否溢出、换行异常、乱码、太小或比例不协调",
    "timestamps": []
  },
  "voice_character_match": {
    "ok": true,
    "severity": "pass|warning|blocker|unknown",
    "evidence": "画面人物与配音声线是否匹配，如性别、年龄感、角色定位",
    "timestamps": []
  },
  "issues": [
    {
      "id": "speech_visual_sync_reviewed|talking_head_motion_continuity|subtitle_text_layout|voice_character_match|main_subject_not_deformed|no_black_frames|no_freeze_events|other",
      "severity": "blocker|warning",
      "timestamp": "00:03",
      "description": "具体问题"
    }
  ],
  "summary": "整体判断"
}
"""


def read_json(path: Path | None, fallback: Any) -> Any:
    if not path or not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_rubric() -> dict:
    return read_json(RUBRIC_PATH, {})


def find_manifest(run_dir: Path | None) -> Path | None:
    if not run_dir:
        return None
    candidates = [
        run_dir / "artifact_manifest.json",
        run_dir / "release_manifest.json",
        run_dir / "public" / "release_manifest.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = sorted(run_dir.glob("**/*manifest*.json"))
    return found[0] if found else None


def find_storyboard(run_dir: Path | None) -> Path | None:
    if not run_dir:
        return None
    candidates = [run_dir / "storyboard.json", run_dir / "internal" / "storyboard.json"]
    for path in candidates:
        if path.exists():
            return path
    found = sorted(run_dir.glob("**/storyboard*.json"))
    return found[0] if found else None


def probe_from_local_qa(local_qa: dict) -> dict:
    return local_qa.get("probe") if isinstance(local_qa.get("probe"), dict) else {}


def run_local_qa(args: argparse.Namespace, final_video: Path | None, run_dir: Path | None, output_dir: Path) -> dict:
    output = output_dir / "local_video_qa.json"
    qa_args = argparse.Namespace(
        run_dir=str(run_dir or ""),
        manifest=str(Path(args.manifest).expanduser().resolve()) if args.manifest else "",
        final_video=str(final_video or ""),
        aspect_ratio=args.aspect_ratio,
        min_duration=args.min_duration,
        aspect_tolerance=args.aspect_tolerance,
        expect_audio=args.expect_audio,
        require_prompts=False,
        json=True,
        output=str(output),
    )
    report = run_local_video_qa(qa_args)
    write_json(output, report)
    return report


def run_ffmpeg_detection(video: Path, filter_expr: str, pattern: str) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video.exists():
        return {"ok": False, "available": bool(ffmpeg), "events": [], "error": "ffmpeg unavailable or video missing"}
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(video), "-vf", filter_expr, "-an", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    events = [line.strip() for line in text.splitlines() if pattern in line]
    return {
        "ok": proc.returncode == 0 or bool(events),
        "available": True,
        "events": events,
        "returncode": proc.returncode,
    }


def make_contact_sheet(video: Path | None, output: Path) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video or not video.exists():
        return {"ok": False, "path": "", "error": "ffmpeg unavailable or video missing"}
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            "fps=1,scale=240:-1,tile=5x6",
            "-frames:v",
            "1",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "ok": proc.returncode == 0 and output.exists(),
        "path": str(output) if output.exists() else "",
        "error": (proc.stderr or proc.stdout or "").strip(),
    }


def manifest_has_category(manifest: dict, category: str) -> bool:
    artifacts = manifest.get("artifacts") or []
    return any(isinstance(item, dict) and item.get("category") == category for item in artifacts)


def manifest_text(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True)


def evidence_text(*payloads: dict | None) -> str:
    chunks: list[str] = []
    for payload in payloads:
        if isinstance(payload, dict) and payload:
            chunks.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return "\n".join(chunks).lower()


def string_values(payload: Any) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            values.extend(string_values(value))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(string_values(item))
    elif isinstance(payload, str) and payload.strip():
        values.append(payload)
    return values


def value_text(*payloads: Any) -> str:
    chunks: list[str] = []
    for payload in payloads:
        chunks.extend(string_values(payload))
    return "\n".join(chunks).lower()


def requires_speech_visual_sync(capsule: dict | None, storyboard: dict, manifest: dict) -> bool:
    if capsule and capsule.get("category") == "digital_human":
        return True
    text = evidence_text(capsule, storyboard, manifest)
    return any(keyword in text for keyword in SPEECH_SYNC_KEYWORDS)


def requires_text_layout_review(capsule: dict | None, storyboard: dict, manifest: dict) -> bool:
    config = (capsule or {}).get("config") or {}
    if config.get("add_subtitles") is True or manifest_has_category(manifest, "subtitle"):
        return True
    text = value_text(storyboard, manifest)
    return any(keyword in text for keyword in TEXT_LAYOUT_KEYWORDS)


def requires_voice_character_review(capsule: dict | None, storyboard: dict, manifest: dict) -> bool:
    config = (capsule or {}).get("config") or {}
    has_voice = bool(config.get("has_narration") or config.get("tts_voice") or config.get("tts_provider"))
    if not has_voice and not requires_speech_visual_sync(capsule, storyboard, manifest):
        return False
    if requires_speech_visual_sync(capsule, storyboard, manifest):
        return True
    text = value_text(storyboard, manifest)
    return any(keyword in text for keyword in VOICE_CHARACTER_KEYWORDS)


def severity_is_blocker(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"blocker", "fatal", "error", "严重", "重度", "失败", "fail", "failed"}


def multimodal_field_result(raw: dict, field_name: str, required: bool) -> dict:
    field = raw.get(field_name) if isinstance(raw.get(field_name), dict) else {}
    if not required:
        return {
            "ok": True,
            "detail": "not applicable",
            "timestamps": [],
        }
    ok = bool(field.get("ok")) and not severity_is_blocker(field.get("severity"))
    ok = ok and str(field.get("severity", "")).lower() != "unknown"
    return {
        "ok": ok,
        "detail": field.get("evidence") or raw.get("summary") or "",
        "timestamps": field.get("timestamps") or [],
    }


def normalize_multimodal_review(
    raw: dict,
    provider: str,
    video_path: Path,
    speech_sync_required: bool,
    text_layout_required: bool,
    voice_character_required: bool,
) -> dict:
    if not raw:
        return {
            "enabled": True,
            "provider": provider,
            "success": False,
            "status": "unavailable",
            "error": "empty multimodal response",
            "checks": {},
            "issues": [],
            "raw": raw,
        }

    issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    blocker_issues = [item for item in issues if isinstance(item, dict) and severity_is_blocker(item.get("severity"))]
    success = bool(raw.get("success"))
    needs_regeneration = bool(raw.get("needs_regeneration"))

    checks = {
        "speech_visual_sync_reviewed": multimodal_field_result(raw, "speech_visual_sync", speech_sync_required),
        "talking_head_motion_continuity": multimodal_field_result(raw, "motion_continuity", speech_sync_required),
        "subtitle_text_layout": multimodal_field_result(raw, "subtitle_text_layout", text_layout_required),
        "voice_character_match": multimodal_field_result(raw, "voice_character_match", voice_character_required),
    }
    required_failed = any(
        not checks[key]["ok"]
        for key, required in {
            "speech_visual_sync_reviewed": speech_sync_required,
            "talking_head_motion_continuity": speech_sync_required,
            "subtitle_text_layout": text_layout_required,
            "voice_character_match": voice_character_required,
        }.items()
        if required
    )

    if not success:
        status = "unavailable"
    elif needs_regeneration or blocker_issues or required_failed:
        status = "failed"
    elif issues:
        status = "needs_review"
    else:
        status = "passed"

    return {
        "enabled": True,
        "provider": provider,
        "success": success,
        "status": status,
        "video_path": str(video_path),
        "quality_score": raw.get("quality_score"),
        "checks": checks,
        "issues": issues,
        "summary": raw.get("summary", ""),
        "error": raw.get("error", ""),
        "raw": raw,
    }


def run_multimodal_review(
    args: argparse.Namespace,
    final_video: Path | None,
    output_dir: Path,
    speech_sync_required: bool,
    text_layout_required: bool,
    voice_character_required: bool,
) -> dict:
    output = Path(args.multimodal_review_output).expanduser().resolve() if args.multimodal_review_output else output_dir / "multimodal_video_review.json"
    if not args.multimodal_review:
        report = {"enabled": False, "status": "skipped", "reason": "not requested"}
        write_json(output, report)
        return report
    if not final_video or not final_video.exists():
        report = {
            "enabled": True,
            "provider": args.multimodal_provider,
            "success": False,
            "status": "skipped",
            "reason": "final video missing",
        }
        write_json(output, report)
        return report

    try:
        if args.multimodal_provider != "gemini3":
            raise ValueError(f"Unsupported multimodal provider: {args.multimodal_provider}")
        from custom_tools.quality_check.gemini3_video_analyzer import Gemini3VideoAnalyzer

        analyzer = Gemini3VideoAnalyzer()
        raw = analyzer.analyze_video(
            video_path=str(final_video),
            prompt=MULTIMODAL_REVIEW_PROMPT,
            analysis_focus="quality",
        )
        report = normalize_multimodal_review(
            raw,
            args.multimodal_provider,
            final_video,
            speech_sync_required,
            text_layout_required,
            voice_character_required,
        )
    except Exception as exc:
        report = {
            "enabled": True,
            "provider": args.multimodal_provider,
            "success": False,
            "status": "unavailable",
            "error": str(exc),
            "checks": {},
            "issues": [],
        }
    write_json(output, report)
    return report


def read_manual_issues(path: str) -> list[dict]:
    if not path:
        return []
    data = read_json(Path(path).expanduser(), [])
    return data if isinstance(data, list) else []


def issue_for_manual(check_id: str, manual_issues: list[dict]) -> dict | None:
    for item in manual_issues:
        if isinstance(item, dict) and item.get("id") == check_id:
            return item
    return None


def build_check_results(
    rubric: dict,
    *,
    local_qa: dict,
    manifest: dict,
    probe: dict,
    capsule: dict | None,
    storyboard: dict,
    blackdetect: dict,
    freezedetect: dict,
    contact_sheet: dict,
    multimodal_review: dict,
    manual_issues: list[dict],
) -> tuple[list[dict], dict]:
    config = (capsule or {}).get("config") or {}
    expected_audio = bool(config.get("has_narration") or config.get("add_background_music"))
    no_audio_expected = capsule is not None and not expected_audio
    expected_subtitles = bool(config.get("add_subtitles"))
    final_video = Path(local_qa.get("final_video") or "") if local_qa.get("final_video") else None
    width = int(probe.get("width") or 0)
    height = int(probe.get("height") or 0)
    duration = float(probe.get("duration") or 0.0)
    route_evidence_text = manifest_text(manifest).lower()
    video_available = bool(final_video and final_video.exists() and probe.get("ok"))
    speech_sync_required = requires_speech_visual_sync(capsule, storyboard, manifest)
    text_layout_required = requires_text_layout_review(capsule, storyboard, manifest)
    voice_character_required = requires_voice_character_review(capsule, storyboard, manifest)
    multimodal_checks = multimodal_review.get("checks") if isinstance(multimodal_review.get("checks"), dict) else {}
    multimodal_success = bool(multimodal_review.get("success"))

    automatic_ok = {
        "final_video_exists": bool(final_video and final_video.exists()),
        "ffprobe_ok": bool(probe.get("ok")),
        "aspect_ratio_ok": any(item.get("id") == "aspect_ratio" and item.get("ok") for item in local_qa.get("checks", [])),
        "duration_ok": video_available and duration >= 6.0,
        "resolution_ok": video_available and width >= 540 and height >= 960,
        "expected_audio_present": video_available and ((not expected_audio) or bool(probe.get("has_audio"))),
        "audio_not_unexpected": video_available and ((not no_audio_expected) or (not probe.get("has_audio"))),
        "subtitle_policy_ok": expected_subtitles or not expected_subtitles,
        "narration_timing_reviewed": not config.get("has_narration"),
        "speech_visual_sync_reviewed": (not speech_sync_required) or bool((multimodal_checks.get("speech_visual_sync_reviewed") or {}).get("ok")),
        "voice_character_match": (not voice_character_required) or bool((multimodal_checks.get("voice_character_match") or {}).get("ok")),
        "bgm_balance_reviewed": not expected_audio,
        "no_black_frames": video_available and bool(blackdetect.get("available")) and len(blackdetect.get("events") or []) == 0,
        "no_freeze_events": video_available and bool(freezedetect.get("available")) and len(freezedetect.get("events") or []) == 0,
        "visual_scan_required": bool(contact_sheet.get("ok")) or multimodal_success,
        "talking_head_motion_continuity": (not speech_sync_required) or bool((multimodal_checks.get("talking_head_motion_continuity") or {}).get("ok")),
        "subtitle_text_layout": (not text_layout_required) or bool((multimodal_checks.get("subtitle_text_layout") or {}).get("ok")),
        "capsule_contract_loaded": capsule is not None,
        "route_truthful": True,
        "audio_route_matches_capsule": True,
        "quality_rules_reviewed": False,
        "manifest_present": bool(manifest),
        "copywriting_present": manifest_has_category(manifest, "copywriting"),
        "review_artifacts_present": bool(contact_sheet.get("ok")) and bool(local_qa),
        "no_remote_or_secret_paths": not REMOTE_OR_SECRET_PATTERN.search(manifest_text(manifest)),
    }
    automatic_detail = {
        check_id: data.get("detail", "")
        for check_id, data in multimodal_checks.items()
        if isinstance(data, dict) and data.get("detail")
    }

    if capsule and capsule_requires_special_route(capsule):
        category = capsule.get("category")
        if category == "action_transfer":
            automatic_ok["route_truthful"] = "action" in route_evidence_text or "runninghub" in route_evidence_text
        elif category == "digital_human":
            automatic_ok["route_truthful"] = "lipsync" in route_evidence_text or "lip_sync" in route_evidence_text or "runninghub" in route_evidence_text
        elif category == "music_mv":
            automatic_ok["route_truthful"] = "suno" in route_evidence_text or "music" in route_evidence_text

    if capsule:
        if config.get("has_narration") is False and probe.get("has_audio") and config.get("add_background_music") is False:
            automatic_ok["audio_route_matches_capsule"] = False
        if capsule.get("category") == "music_mv" and config.get("has_narration"):
            automatic_ok["audio_route_matches_capsule"] = False

    if storyboard:
        scenes = storyboard.get("storyboard") or []
        automatic_ok["structure_matches_capsule"] = bool(scenes)
        automatic_ok["style_matches_capsule"] = bool(scenes)
    else:
        automatic_ok["structure_matches_capsule"] = False
        automatic_ok["style_matches_capsule"] = False

    results: list[dict] = []
    category_scores: dict[str, dict] = {}
    for category in rubric.get("categories", []):
        category_id = category["id"]
        category_score = 0
        max_points = int(category.get("max_points") or 0)
        for check in category.get("checks", []):
            check_id = check["id"]
            points = int(check.get("points") or 0)
            manual_issue = issue_for_manual(check_id, manual_issues)
            manual_only = str(check.get("severity", "")).startswith("manual")
            applies_when = check.get("applies_when")
            not_applicable = (
                (applies_when == "speech_visual_sync" and not speech_sync_required)
                or (applies_when == "text_layout" and not text_layout_required)
                or (applies_when == "voice_character" and not voice_character_required)
            )
            if manual_issue:
                ok = bool(manual_issue.get("ok", False))
                detail = manual_issue.get("detail") or manual_issue.get("message") or ("manual pass" if ok else "manual issue")
                severity = manual_issue.get("severity") or check.get("severity", "warning")
            elif not_applicable:
                ok = True
                detail = "not applicable"
                severity = check.get("severity", "warning")
            elif manual_only and check_id in automatic_ok:
                ok = bool(automatic_ok.get(check_id, False))
                detail = automatic_detail.get(check_id) or (
                    "multimodal review passed" if ok else "multimodal review required"
                )
                severity = check.get("severity", "warning") if not ok else check.get("severity", "warning")
            elif manual_only:
                ok = False
                detail = "manual review required"
                severity = "manual_review_required"
            else:
                ok = bool(automatic_ok.get(check_id, False))
                detail = ""
                severity = check.get("severity", "warning")
            earned = points if ok else 0
            category_score += earned
            results.append(
                {
                    "id": check_id,
                    "category": category_id,
                    "label": category.get("label", category_id),
                    "ok": ok,
                    "points": points,
                    "earned": earned,
                    "severity": severity,
                    "common_issue": check.get("common_issue"),
                    "description": check.get("description", ""),
                    "detail": detail,
                }
            )
        category_scores[category_id] = {
            "label": category.get("label", category_id),
            "score": category_score,
            "max_points": max_points,
        }
    return results, category_scores


def score_status(score: int, blockers: list[dict], rubric: dict) -> str:
    if blockers:
        return "fail"
    bands = rubric.get("score_bands") or {}
    if score >= int(bands.get("pass", 85)):
        return "pass"
    if score >= int(bands.get("needs_review", 70)):
        return "needs_review"
    return "fail"


def edit_plan_validation_issues(edit_plan_validation: dict) -> tuple[list[dict], list[dict]]:
    if not edit_plan_validation:
        return [], []

    def convert(item: dict, severity: str) -> dict:
        return {
            "id": item.get("id", "edit_plan_validation"),
            "category": "edit_plan_contract",
            "label": "时间线合同",
            "ok": False,
            "points": 0,
            "earned": 0,
            "severity": severity,
            "common_issue": "edit_plan_contract_failed",
            "description": item.get("message") or "EditPlan timeline contract failed.",
            "detail": item.get("detail") or "",
        }

    blockers = edit_plan_validation.get("blockers")
    warnings = edit_plan_validation.get("warnings")
    converted_blockers = [
        convert(item, "blocker")
        for item in blockers
        if isinstance(item, dict)
    ] if isinstance(blockers, list) else []
    converted_warnings = [
        convert(item, "warning")
        for item in warnings
        if isinstance(item, dict)
    ] if isinstance(warnings, list) else []
    return converted_blockers, converted_warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--final-video", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--storyboard", default="")
    parser.add_argument("--edit-plan-validation", default="")
    parser.add_argument("--capsule", default="", help="本地 SQLite 胶囊短名")
    parser.add_argument("--capsule-db", default="")
    parser.add_argument("--aspect-ratio", default="9:16")
    parser.add_argument("--min-duration", type=float, default=6.0)
    parser.add_argument("--aspect-tolerance", type=float, default=0.08)
    parser.add_argument("--expect-audio", action="store_true")
    parser.add_argument("--manual-issues-json", default="")
    parser.add_argument(
        "--multimodal-review",
        action="store_true",
        help="Run a video-reading multimodal review and map the result into QA gates.",
    )
    parser.add_argument(
        "--multimodal-provider",
        default="gemini3",
        choices=["gemini3"],
        help="Multimodal video reviewer provider. Default: gemini3.",
    )
    parser.add_argument("--multimodal-review-output", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        run_dir = require_workspace_under_output(args.run_dir) if args.run_dir else None
        output = require_under_output(args.output, "--output") if args.output else None
        if args.multimodal_review_output:
            args.multimodal_review_output = str(
                require_under_output(args.multimodal_review_output, "--multimodal-review-output")
            )
    except ValueError as exc:
        raise SystemExit(f"错误：{exc}") from exc
    output_dir = (
        run_dir / "qa"
        if run_dir
        else (
            output.parent
            if output
            else OUTPUT_ROOT / f"manual_video_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}" / "qa"
        )
    )
    final_video = Path(args.final_video).expanduser().resolve() if args.final_video else None
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else find_manifest(run_dir)
    storyboard_path = Path(args.storyboard).expanduser().resolve() if args.storyboard else find_storyboard(run_dir)
    edit_plan_validation_path = (
        Path(args.edit_plan_validation).expanduser().resolve()
        if args.edit_plan_validation
        else (run_dir / "qa" / "edit_plan_validation.json" if run_dir else None)
    )
    manifest = read_json(manifest_path, {}) if manifest_path else {}
    storyboard = read_json(storyboard_path, {}) if storyboard_path else {}
    edit_plan_validation = read_json(edit_plan_validation_path, {}) if edit_plan_validation_path else {}
    capsule = load_capsule(args.capsule, args.capsule_db) if args.capsule else None
    if capsule:
        cfg = capsule.get("config") or {}
        if not args.expect_audio and (cfg.get("has_narration") or cfg.get("add_background_music")):
            args.expect_audio = True
        if not args.final_video and not final_video and manifest:
            for item in manifest.get("artifacts", []):
                if isinstance(item, dict) and item.get("category") == "final_video" and item.get("path"):
                    final_video = Path(item["path"]).expanduser().resolve()
                    break

    local_qa = run_local_qa(args, final_video, run_dir, output_dir)
    if not final_video and local_qa.get("final_video"):
        final_video = Path(local_qa["final_video"]).expanduser().resolve()
    probe = probe_from_local_qa(local_qa)
    blackdetect = run_ffmpeg_detection(final_video, "blackdetect=d=0.25:pix_th=0.10", "black_start") if final_video else {}
    freezedetect = run_ffmpeg_detection(final_video, "freezedetect=n=-60dB:d=1.2", "freeze_start") if final_video else {}
    contact_sheet = make_contact_sheet(final_video, output_dir / "review_contact_sheet.jpg")
    speech_sync_required = requires_speech_visual_sync(capsule, storyboard, manifest)
    text_layout_required = requires_text_layout_review(capsule, storyboard, manifest)
    voice_character_required = requires_voice_character_review(capsule, storyboard, manifest)
    multimodal_review = run_multimodal_review(
        args,
        final_video,
        output_dir,
        speech_sync_required,
        text_layout_required,
        voice_character_required,
    )
    rubric = load_rubric()
    manual_issues = read_manual_issues(args.manual_issues_json)
    checks, category_scores = build_check_results(
        rubric,
        local_qa=local_qa,
        manifest=manifest,
        probe=probe,
        capsule=capsule,
        storyboard=storyboard,
        blackdetect=blackdetect,
        freezedetect=freezedetect,
        contact_sheet=contact_sheet,
        multimodal_review=multimodal_review,
        manual_issues=manual_issues,
    )
    score = sum(item["earned"] for item in checks)
    blockers = [
        item for item in checks
        if not item["ok"] and item.get("severity") in {"blocker", "manual_blocker"}
    ]
    warnings = [
        item for item in checks
        if not item["ok"] and item.get("severity") not in {"blocker", "manual_blocker"}
    ]
    edit_plan_blockers, edit_plan_warnings = edit_plan_validation_issues(edit_plan_validation)
    blockers.extend(edit_plan_blockers)
    warnings.extend(edit_plan_warnings)
    common_issues = rubric.get("common_issues") or {}
    report = {
        "ok": not blockers and score >= int((rubric.get("score_bands") or {}).get("needs_review", 70)),
        "status": score_status(score, blockers, rubric),
        "score": score,
        "score_max": sum(int(cat.get("max_points") or 0) for cat in rubric.get("categories", [])),
        "category_scores": category_scores,
        "capsule": {
            "name": capsule.get("name") if capsule else "",
            "category": capsule.get("category") if capsule else "",
            "status": capsule.get("status") if capsule else "",
        },
        "run_dir": str(run_dir) if run_dir else "",
        "final_video": str(final_video) if final_video else "",
        "manifest_path": str(manifest_path) if manifest_path else "",
        "storyboard_path": str(storyboard_path) if storyboard_path else "",
        "edit_plan_validation_path": str(edit_plan_validation_path) if edit_plan_validation_path else "",
        "edit_plan_validation": edit_plan_validation,
        "contact_sheet": contact_sheet,
        "local_video_qa_path": str(output_dir / "local_video_qa.json"),
        "blackdetect": blackdetect,
        "freezedetect": freezedetect,
        "multimodal_review_path": str(Path(args.multimodal_review_output).expanduser().resolve()) if args.multimodal_review_output else str(output_dir / "multimodal_video_review.json"),
        "multimodal_review": multimodal_review,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "common_issue_checklist": common_issues,
        "manual_review_required": [
            item for item in checks
            if not item["ok"] and str(item.get("severity", "")).startswith("manual")
        ],
    }
    output = output or (output_dir / "video_quality_score.json")
    write_json(output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"video_quality_score: {report['status']} {score}/{report['score_max']}")
        if blockers:
            print("blockers:")
            for item in blockers:
                print(f"- {item['id']}: {item['description']}")
        if warnings:
            print("warnings:")
            for item in warnings[:10]:
                print(f"- {item['id']}: {item['description']}")
        print(f"report: {output}")
        if contact_sheet.get("path"):
            print(f"contact_sheet: {contact_sheet['path']}")
        if multimodal_review.get("enabled"):
            print(f"multimodal_review: {multimodal_review.get('status')} ({report['multimodal_review_path']})")
    sys.exit(0 if report["status"] != "fail" else 1)


if __name__ == "__main__":
    main()
