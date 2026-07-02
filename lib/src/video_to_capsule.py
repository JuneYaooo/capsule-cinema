from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


BREAKDOWN_SCHEMA = "capsule_cinema.video_breakdown.v1"
DRAFT_SCHEMA = "capsule_cinema.capsule_draft.v1"
SAFE_CAPSULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RECIPE_DOMAINS = ("structure", "copy", "visual", "audio", "motion")
RECIPE_STAGE = {
    "structure": "planning",
    "copy": "planning",
    "visual": "planning",
    "audio": "planning",
    "motion": "generation",
}
RECIPE_TITLE = {
    "structure": "Structure Recipe",
    "copy": "Copy Recipe",
    "visual": "Visual Recipe",
    "audio": "Audio Recipe",
    "motion": "Motion Recipe",
}


class VideoToCapsuleError(Exception):
    """Raised when source video analysis cannot produce a usable capsule draft."""


def _as_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def _strings(value: Any) -> list[str]:
    result: list[str] = []
    for item in _as_list(value):
        text = _as_text(item)
        if text:
            result.append(text)
    return result


def _slug(value: str, default: str = "video_capsule") -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    if not text:
        text = default
    if not re.match(r"^[A-Za-z0-9]", text):
        text = f"capsule_{text}"
    return text


def _safe_capsule_name(value: str, source_video_path: str) -> str:
    name = _slug(value or Path(source_video_path).stem)
    if not SAFE_CAPSULE_NAME.fullmatch(name):
        raise VideoToCapsuleError(f"unsafe capsule name: {name}")
    return name


def _title_from_name(name: str) -> str:
    words = re.split(r"[_-]+", name)
    return " ".join(word.capitalize() for word in words if word) or name


def _parse_jsonish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if value.get("raw_response") and not (value.get("segments") or value.get("capsule_recipe")):
            raw_response = value.get("raw_response")
            try:
                parsed = _parse_jsonish(raw_response)
            except VideoToCapsuleError:
                return value
            return {**value, **parsed}
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise VideoToCapsuleError("empty analyzer response")
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise VideoToCapsuleError("analyzer response did not contain a JSON object")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise VideoToCapsuleError(f"invalid analyzer JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise VideoToCapsuleError("analyzer JSON must be an object")
        return parsed
    raise VideoToCapsuleError("analyzer response must be a dict or JSON string")


def _normalize_segments(segments: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(_as_list(segments), start=1):
        if isinstance(item, dict):
            segment = {
                "index": index,
                "start_time": _as_text(item.get("start_time")),
                "end_time": _as_text(item.get("end_time")),
                "beat": _as_text(item.get("beat") or item.get("summary")),
                "visuals": _as_text(item.get("visuals")),
                "motion": _as_text(item.get("motion")),
                "copy": _as_text(item.get("copy")),
                "audio": _as_text(item.get("audio")),
                "reuse_lesson": _as_text(item.get("reuse_lesson") or item.get("lesson")),
            }
        else:
            segment = {
                "index": index,
                "start_time": "",
                "end_time": "",
                "beat": _as_text(item),
                "visuals": "",
                "motion": "",
                "copy": "",
                "audio": "",
                "reuse_lesson": "",
            }
        normalized.append(segment)
    return normalized


def _quality_rules(values: Any) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for index, item in enumerate(_as_list(values), start=1):
        if isinstance(item, dict):
            rule = dict(item)
            rule.setdefault("id", f"inferred_quality_rule_{index}")
            rule.setdefault("type", "manual_qc_required")
            rule.setdefault("severity", "warning")
            if "rule" not in rule:
                rule["rule"] = _as_text(rule.get("description") or rule.get("summary"))
        else:
            rule = {
                "id": f"inferred_quality_rule_{index}",
                "type": "manual_qc_required",
                "severity": "warning",
                "rule": _as_text(item),
            }
        if _as_text(rule.get("rule")):
            rules.append(rule)
    return rules


def _lessons_from_segments(segments: list[dict[str, str]]) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    for segment in segments:
        lesson = segment.get("reuse_lesson")
        if not lesson:
            continue
        lessons.append(
            {
                "id": f"segment_{segment['index']}_reuse_lesson",
                "scope": "structure",
                "rule": lesson,
                "applies_when": ["video-analysis", "similar-source-video"],
            }
        )
    return lessons


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _as_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def build_analysis_prompt(analysis_prompt: str = "", target_platform: str = "") -> str:
    platform_line = f"Target platform hint: {target_platform}\n" if target_platform else ""
    custom_line = f"\nAdditional user analysis request:\n{analysis_prompt.strip()}\n" if analysis_prompt else ""
    return (
        "Analyze the local source video and return only a JSON object. "
        "Do not include markdown fences or prose outside JSON.\n"
        f"{platform_line}"
        "Required shape:\n"
        "{\n"
        '  "summary": "short source video summary",\n'
        '  "source_profile": {"likely_format": "short_video|explainer|product_showcase|story|music_mv|other", "aspect_ratio": "9:16|16:9|1:1|unknown", "target_platform": "", "primary_audience": ""},\n'
        '  "segments": [{"start_time": "00:00.000", "end_time": "00:03.000", "beat": "", "visuals": "", "motion": "", "copy": "", "audio": "", "reuse_lesson": ""}],\n'
        '  "capsule_recipe": {"when_to_use": [], "when_not_to_use": [], "structure_rules": [], "copy_rules": [], "visual_rules": [], "audio_rules": [], "motion_rules": [], "quality_rules": [], "default_runtime": {}},\n'
        '  "warnings": []\n'
        "}\n"
        f"{custom_line}"
    )


def normalize_video_analysis(
    raw_result: dict[str, Any] | str,
    *,
    source_video_path: str,
    analysis_tool: str,
    capsule_name: str = "",
    capsule_display_name: str = "",
    capsule_summary: str = "",
    target_platform: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = _parse_jsonish(raw_result)
    if raw.get("success") is False:
        raise VideoToCapsuleError(str(raw.get("error") or "video analysis failed"))

    source = Path(source_video_path).expanduser()
    if not source.is_file():
        raise VideoToCapsuleError(f"source video not found: {source}")

    summary = _as_text(capsule_summary or raw.get("summary") or raw.get("description"), "Inferred video capsule draft.")
    source_profile = raw.get("source_profile") if isinstance(raw.get("source_profile"), dict) else {}
    if target_platform and not source_profile.get("target_platform"):
        source_profile["target_platform"] = target_platform
    segments = _normalize_segments(raw.get("segments") or raw.get("scene_breakdown") or [])
    recipe = raw.get("capsule_recipe") if isinstance(raw.get("capsule_recipe"), dict) else {}
    warnings = _strings(raw.get("warnings"))
    safe_name = _safe_capsule_name(capsule_name, str(source))
    display_name = _as_text(capsule_display_name, _title_from_name(safe_name))
    category = _slug(_as_text(source_profile.get("likely_format"), "video_to_capsule"), "video_to_capsule")
    default_runtime = recipe.get("default_runtime") if isinstance(recipe.get("default_runtime"), dict) else {}

    recipes = {
        "structure": _strings(recipe.get("structure_rules")),
        "copy": _strings(recipe.get("copy_rules")),
        "visual": _strings(recipe.get("visual_rules")),
        "audio": _strings(recipe.get("audio_rules")),
        "motion": _strings(recipe.get("motion_rules")),
    }
    if not recipes["structure"]:
        lessons = [segment["reuse_lesson"] for segment in segments if segment.get("reuse_lesson")]
        recipes["structure"] = _dedupe(lessons) or ["Use the analyzed source video's clearest reusable hook and pacing pattern."]

    quality_rules = _quality_rules(recipe.get("quality_rules"))
    if not quality_rules:
        quality_rules = [
            {
                "id": "inferred_source_pattern_review",
                "type": "manual_qc_required",
                "severity": "warning",
                "rule": "Review generated outputs against the inferred structure, visual, copy, audio, and motion rules before release.",
            }
        ]

    when_to_use = _strings(recipe.get("when_to_use")) or [f"Use for {category.replace('_', ' ')} videos with a similar source pattern."]
    when_not_to_use = _strings(recipe.get("when_not_to_use"))
    platform_tag = _slug(_as_text(source_profile.get("target_platform")), "")
    tags = _dedupe(
        [
            "video-analysis",
            "ai-video",
            category,
            platform_tag,
        ]
    )
    capabilities = _dedupe(["image_to_video", "tts", "bgm"])

    breakdown = {
        "schema_version": BREAKDOWN_SCHEMA,
        "source_video": {
            "path": str(source),
            "filename": source.name,
        },
        "analysis_tool": analysis_tool,
        "summary": summary,
        "source_profile": source_profile,
        "segments": segments,
        "warnings": warnings,
    }
    draft = {
        "schema_version": DRAFT_SCHEMA,
        "name": safe_name,
        "display_name": display_name,
        "summary": summary,
        "category": category,
        "primary_workflow": "generic_ai_video",
        "capabilities": capabilities,
        "tags": tags,
        "when_to_use": when_to_use,
        "when_not_to_use": when_not_to_use,
        "input_schema": {
            "fields": {
                "topic": {
                    "type": "string",
                    "required": True,
                    "description": "Primary topic for videos made with this inferred capsule.",
                }
            }
        },
        "runtime": {
            "defaults": default_runtime,
            "output_contract": {"final_video": "required"},
        },
        "recipes": recipes,
        "quality_rules": quality_rules,
        "lessons": _lessons_from_segments(segments),
        "analysis": {
            "tool": analysis_tool,
            "source_summary": summary,
            "segment_count": len(segments),
        },
    }
    return breakdown, draft


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_artifact_manifest(workspace_dir: Path, artifacts: list[dict[str, Any]]) -> Path:
    manifest = {
        "schema_version": 1,
        "workflow": "video_to_capsule",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifacts": artifacts,
    }
    return write_json(workspace_dir / "artifact_manifest.json", manifest)


def _dump_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


def _frontmatter(meta: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).strip() + "\n---\n\n" + body.rstrip() + "\n"


def _recipe_markdown(domain: str, rules: list[str]) -> str:
    meta = {
        "type": "Video Recipe",
        "title": RECIPE_TITLE[domain],
        "description": f"Inferred {domain} rules from source video analysis.",
        "stage": RECIPE_STAGE[domain],
        "domain": domain,
        "profile": "video.okf.capsule.v1",
        "tags": [domain, "video-analysis"],
    }
    body_lines = [f"# {domain.title()}", "", "## Rules", ""]
    if rules:
        body_lines.extend(f"- {rule}" for rule in rules)
    else:
        body_lines.append("- Use the global video production policy for this domain.")
    return _frontmatter(meta, "\n".join(body_lines))


def _rewrite_package_surfaces(cap_dir: Path, draft: dict[str, Any]) -> None:
    from capsule_package_create import render_card_markdown, render_index_markdown

    capsule_path = cap_dir / "capsule.yaml"
    capsule = yaml.safe_load(capsule_path.read_text(encoding="utf-8")) or {}
    capsule["summary"] = draft["summary"]
    capsule["category"] = draft["category"]
    capsule["primary_workflow"] = draft["primary_workflow"]
    capsule["capabilities"] = draft["capabilities"]
    capsule["tags"] = draft["tags"]
    capsule["when_to_use"] = draft["when_to_use"]
    capsule["when_not_to_use"] = draft["when_not_to_use"]
    _dump_yaml(capsule_path, capsule)
    (cap_dir / "index.md").write_text(render_index_markdown(capsule), encoding="utf-8")
    (cap_dir / "CARD.md").write_text(render_card_markdown(capsule), encoding="utf-8")
    _dump_yaml(cap_dir / "contracts" / "input_schema.yaml", draft["input_schema"])
    _dump_yaml(
        cap_dir / "contracts" / "runtime.yaml",
        {
            "roles": {},
            "output_contract": draft["runtime"].get("output_contract") or {"final_video": "required"},
            "defaults": draft["runtime"].get("defaults") or {},
        },
    )
    for domain in RECIPE_DOMAINS:
        (cap_dir / "recipes" / f"{domain}.md").write_text(
            _recipe_markdown(domain, _strings((draft.get("recipes") or {}).get(domain))),
            encoding="utf-8",
        )
    _dump_yaml(cap_dir / "quality" / "rules.yaml", {"rules": draft.get("quality_rules") or []})
    _dump_yaml(cap_dir / "learning" / "promoted_lessons.yaml", {"lessons": draft.get("lessons") or []})


def materialize_capsule_from_draft(
    draft: dict[str, Any],
    *,
    source_video_path: str,
    output_root: str | Path,
    include_source_video: bool = False,
    overwrite: bool = False,
) -> Path:
    from capsule_package_create import create_capsule_package
    from capsule_package_validate import validate_capsule_dir

    source = Path(source_video_path).expanduser()
    if not source.is_file():
        raise VideoToCapsuleError(f"source video not found: {source}")
    cap_dir = create_capsule_package(
        output_root=output_root,
        name=draft["name"],
        display_name=draft["display_name"],
        summary=draft["summary"],
        category=draft["category"],
        primary_workflow=draft["primary_workflow"],
        capabilities=draft["capabilities"],
        tags=draft["tags"],
        status="active",
        execution_mode="preset",
        overwrite=overwrite,
    )
    _rewrite_package_surfaces(cap_dir, draft)
    if include_source_video:
        dest = cap_dir / "assets" / f"source_video{source.suffix.lower() or '.mp4'}"
        shutil.copy2(source, dest)
        _dump_yaml(
            cap_dir / "assets" / "index.yaml",
            {
                "assets": [
                    {
                        "key": "source_video_reference",
                        "role": "source_video_reference",
                        "reuse": "reference_only",
                        "path": dest.name,
                        "description": "Source video used to infer this capsule; reference only, not reused as final media.",
                        "tags": ["source-video", "video-analysis"],
                    }
                ]
            },
        )
    report = validate_capsule_dir(cap_dir, warnings_ok=True)
    if not report["ok"]:
        raise VideoToCapsuleError("created capsule failed validation: " + "; ".join(report["errors"]))
    return cap_dir
