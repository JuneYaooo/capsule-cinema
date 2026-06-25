#!/usr/bin/env python3
"""Helpers for applying local SQLite capsules to runtime wrapper calls."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR

DEFAULT_DB_CANDIDATES = [
    lambda: os.environ.get("VIDEO_CAPSULE_DB"),
    lambda: str(PROJECT_ROOT / "artifacts" / "capsules" / "initial_capsules.sqlite"),
    lambda: str(Path.home() / ".codex" / "video-production" / "capsules.sqlite"),
]

ENGINE_CLASS_TO_RUNTIME = {
    "SeedanceVideoGeneratorTool": "seedance",
    "SeedanceFastVideoGeneratorTool": "seedance-fast",
    "Jimeng35ProVideoGeneratorTool": "jimeng35pro",
    "Veo3VideoGeneratorTool": "veo3",
    "Veo31VideoGeneratorTool": "veo3.1",
    "GrokVideoGeneratorTool": "grok",
}
IMAGE_ENGINE_CLASS_TO_RUNTIME = {
    "Seedream5ImageGeneratorTool": "seedream5",
    "GptImage2Tool": "gpt-image-2",
    "Gemini3ProImageGeneratorTool": "gemini3_pro",
}
IMAGE_FALLBACK_VIDEO_SENTINELS = {"none_for_default_route", "image-fallback", "image_fallback"}
STILL_IMAGE_KEN_BURNS_ROUTE = "still_images_with_ken_burns"

SPECIAL_ROUTE_CATEGORIES = {"action_transfer", "digital_human", "music_mv"}
BGM_ASSET_ROLES = {"bgm", "music", "audio", "background_music"}


def canonical_capsule_name(name: str) -> str:
    return str(name or "").strip()


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def resolve_capsule_db(explicit_db: str = "") -> Path:
    if explicit_db:
        return Path(explicit_db).expanduser().resolve()
    for getter in DEFAULT_DB_CANDIDATES:
        value = getter()
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if path.exists():
            return path
    return Path.home() / ".codex" / "video-production" / "capsules.sqlite"


def load_capsule(name: str, db_path: str = "") -> dict:
    requested_name = str(name or "").strip()
    path = resolve_capsule_db(db_path)
    if not path.exists():
        raise SystemExit(f"Capsule DB not found: {path}")
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = None
        tried_names = []
        for candidate in capsule_name_candidates(requested_name):
            tried_names.append(candidate)
            row = conn.execute("SELECT * FROM capsules WHERE name = ?", (candidate,)).fetchone()
            if row:
                break
    if not row:
        tried = ", ".join(tried_names) if tried_names else requested_name
        raise SystemExit(f"Capsule not found: {requested_name} in {path}; tried: {tried}")
    payload = {
        "name": canonical_capsule_name(row["name"]),
        "display_name": row["display_name"],
        "status": row["status"],
        "execution_mode": row["execution_mode"],
        "description": row["description"],
        "category": row["category"],
        "tags": _json_load(row["tags_json"], []),
        "config": _json_load(row["config_json"], {}),
        "method": _json_load(row["method_json"], {}),
        "input_schema": _json_load(row["input_schema_json"], {}),
        "quality_rules": _json_load(row["quality_rules_json"], []),
        "local_assets": _json_load(row["local_assets_json"], []),
        "examples": _json_load(row["examples_json"], []) if "examples_json" in row.keys() else [],
        "local_script_path": row["local_script_path"],
        "version": int(row["version"] or 1),
        "db_path": str(path),
    }
    return payload


def capsule_name_candidates(name: str) -> list[str]:
    normalized = canonical_capsule_name(name)
    return [normalized] if normalized else []


def _asset_tags(asset: dict[str, Any]) -> set[str]:
    tags = asset.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {str(item).strip().lower() for item in tags if str(item).strip()}


def _asset_path(asset: dict[str, Any]) -> str:
    path = str(asset.get("path") or "").strip()
    if not path:
        return ""
    return str(Path(path).expanduser())


def asset_exists(asset: dict[str, Any]) -> bool:
    path = _asset_path(asset)
    return bool(path and Path(path).is_file())


def summarize_local_assets(capsule: dict, *, limit: int = 24) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for asset in (capsule.get("local_assets") or [])[:limit]:
        if not isinstance(asset, dict):
            continue
        path = _asset_path(asset)
        summary.append(
            {
                "key": asset.get("key") or "",
                "role": asset.get("role") or "asset",
                "reuse": str(asset.get("reuse") or "reference_only").strip().lower(),
                "path": path,
                "description": asset.get("description") or "",
                "tags": sorted(_asset_tags(asset)),
                "exists": bool(path and Path(path).is_file()),
            }
        )
    return summary


def split_assets_by_reuse(capsule: dict, *, limit: int = 24) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split local assets into (fixed reuse=always, reference_only) groups."""
    fixed: list[dict[str, Any]] = []
    reference: list[dict[str, Any]] = []
    for asset in summarize_local_assets(capsule, limit=limit):
        if asset.get("reuse") == "always":
            fixed.append(asset)
        else:
            reference.append(asset)
    return fixed, reference


def select_default_bgm_asset(capsule: dict) -> dict[str, Any] | None:
    config = capsule.get("config") or {}
    preferred = {
        str(config.get("default_bgm_asset") or "").strip(),
        str(config.get("bgm_asset_filename") or "").strip(),
        str(config.get("default_bgm_key") or "").strip(),
    }
    preferred.discard("")

    candidates: list[dict[str, Any]] = []
    for asset in capsule.get("local_assets") or []:
        if not isinstance(asset, dict):
            continue
        role = str(asset.get("role") or "").strip().lower()
        reuse = str(asset.get("reuse") or "reference_only").strip().lower()
        path = _asset_path(asset)
        if role not in BGM_ASSET_ROLES or reuse != "always" or not path or not Path(path).is_file():
            continue
        candidates.append(asset)

    def score(asset: dict[str, Any]) -> tuple[int, str]:
        path = _asset_path(asset)
        key = str(asset.get("key") or "")
        basename = Path(path).name
        tags = _asset_tags(asset)
        is_preferred = key in preferred or basename in preferred
        is_default = "default" in tags or "default" in key.lower()
        return (2 if is_preferred else 1 if is_default else 0, key or basename)

    if not candidates:
        return None
    return sorted(candidates, key=score, reverse=True)[0]


def capsule_runtime_defaults(capsule: dict) -> dict:
    config = capsule.get("config") or {}
    output_contract = config.get("output_contract") or {}
    roles = config.get("roles") or {}
    defaults: dict[str, Any] = {}
    if config.get("aspect_ratio"):
        defaults["aspect_ratio"] = config["aspect_ratio"]
    if output_contract.get("subtitle") == "none":
        defaults["add_subtitles"] = False
    elif output_contract.get("subtitle") in {"overlay", "burned"}:
        defaults["add_subtitles"] = True
    if output_contract.get("bgm") == "none":
        defaults["add_background_music"] = False
    elif output_contract.get("bgm") == "external":
        defaults["add_background_music"] = True
    if "add_subtitles" in config:
        defaults["add_subtitles"] = bool(config["add_subtitles"])
    if "add_background_music" in config:
        defaults["add_background_music"] = bool(config["add_background_music"])
    if config.get("bgm_volume") is not None:
        defaults["bgm_volume"] = config["bgm_volume"]
    if config.get("voice_volume") is not None:
        defaults["voice_volume"] = config["voice_volume"]
    for key in ("background_music_path", "bgm_path", "music_path"):
        value = config.get(key)
        if isinstance(value, str) and value.strip() and Path(value).expanduser().is_file():
            defaults["background_music_path"] = str(Path(value).expanduser())
            break
    if "background_music_path" not in defaults:
        bgm_asset = select_default_bgm_asset(capsule)
        if bgm_asset:
            defaults["background_music_path"] = _asset_path(bgm_asset)
            defaults["background_music_asset_key"] = bgm_asset.get("key") or ""
    image_role = roles.get("image") if isinstance(roles, dict) else {}
    image_engine = str(
        config.get("image_engine")
        or (image_role or {}).get("selected")
        or (image_role or {}).get("validated_with")
        or ""
    ).strip()
    runtime_image_engine = IMAGE_ENGINE_CLASS_TO_RUNTIME.get(image_engine, image_engine)
    if runtime_image_engine:
        defaults["image_engine"] = runtime_image_engine

    video_role = roles.get("video") if isinstance(roles, dict) else {}
    video_engine_config = str(
        config.get("video_engine")
        or (video_role or {}).get("selected")
        or (video_role or {}).get("validated_with")
        or ""
    ).strip()
    visual_generation_type = str(config.get("visual_generation_type") or "").strip()
    force_image_fallback = (
        video_engine_config in IMAGE_FALLBACK_VIDEO_SENTINELS
        or visual_generation_type == STILL_IMAGE_KEN_BURNS_ROUTE
    )
    if force_image_fallback:
        defaults["force_image_fallback_video"] = True
        defaults["video_generation_route"] = STILL_IMAGE_KEN_BURNS_ROUTE

    runtime_engine = ENGINE_CLASS_TO_RUNTIME.get(video_engine_config)
    if runtime_engine and not force_image_fallback:
        defaults["video_engine"] = runtime_engine
    target_duration = config.get("target_duration")
    if isinstance(target_duration, (int, float)) and target_duration > 0:
        defaults["target_duration"] = int(target_duration)
    return defaults


def capsule_requires_special_route(capsule: dict) -> bool:
    return (capsule.get("category") or "") in SPECIAL_ROUTE_CATEGORIES


def build_capsule_prompt(capsule: dict, user_requirements: str) -> str:
    config = capsule.get("config") or {}
    method = capsule.get("method") or {}
    quality_rules = capsule.get("quality_rules") or []

    def lines_from(key: str) -> list[str]:
        value = method.get(key) or []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value if item]

    compact_config = {
        "aspect_ratio": config.get("aspect_ratio"),
        "target_duration": config.get("target_duration"),
        "target_duration_range": config.get("target_duration_range"),
        "has_narration": config.get("has_narration"),
        "add_subtitles": config.get("add_subtitles"),
        "add_background_music": config.get("add_background_music"),
        "tts_provider": config.get("tts_provider"),
        "tts_voice": config.get("tts_voice"),
        "tts_speed": config.get("tts_speed"),
        "bgm_strategy": config.get("bgm_strategy"),
        "bgm_volume": config.get("bgm_volume"),
        "visual_style": config.get("visual_style"),
        "motion_style": config.get("motion_style"),
        "style_contract": config.get("style_contract"),
        "layout_strategy": config.get("layout_strategy"),
        "music_is_timing_master": config.get("music_is_timing_master"),
    }
    compact_config = {key: value for key, value in compact_config.items() if value is not None}
    fixed_assets, reference_assets = split_assets_by_reuse(capsule)
    examples = capsule.get("examples") or []

    hard_rules = []
    if config.get("has_narration") is False:
        hard_rules.append("默认不要旁白，不要生成 TTS 配音；除非用户显式要求旁白。")
    if config.get("add_subtitles") is False:
        hard_rules.append("默认不要字幕；不要为了模板自动加字幕。")
    if config.get("add_background_music") is False:
        hard_rules.append("默认不要额外背景音乐；如果是 MV，音乐本身是主音频。")
    if fixed_assets:
        hard_rules.append("必须使用 fixed_assets 中声明的固定本地素材（reuse=always）；不要用远程占位或重新生成替换它们。")
    if reference_assets:
        hard_rules.append("reference_assets 仅用于风格/质量对齐；必须按本期主题重新生成，禁止直接复用其内容。")
    if examples:
        hard_rules.append("examples 仅示意；必须按本期主题重新创作，不可直接照搬其中的具体内容。")
    if config.get("has_narration") is True:
        hard_rules.append("旁白视频必须以 TTS 实际时长为时间基准，画面不能短于或长于旁白形成冻结尾巴或静音尾巴。")
    if capsule_requires_special_route(capsule):
        hard_rules.append("该胶囊需要专用路线；普通图生视频只能用于分镜/预览，不能冒充最终专用动作、口播同步或音乐 MV 成片。")

    prompt = {
        "user_requirements": user_requirements,
        "capsule": {
            "name": capsule.get("name"),
            "display_name": capsule.get("display_name"),
            "purpose": capsule.get("description"),
            "category": capsule.get("category"),
            "delivery_promise": config.get("delivery_promise"),
            "config": compact_config,
            "inputs": capsule.get("input_schema") or {},
            "method": method,
            "structure": lines_from("structure"),
            "routing_rules": lines_from("routing_rules"),
            "prompt_rules": lines_from("prompt_rules"),
            "style_rules": lines_from("style_rules"),
            "copy_rules": lines_from("copy_rules"),
            "fixed_assets": fixed_assets,
            "reference_assets": reference_assets,
            "examples": examples,
            "quality_rules": [
                {"id": item.get("id"), "rule": item.get("rule"), "severity": item.get("severity")}
                for item in quality_rules
                if isinstance(item, dict)
            ],
            "hard_runtime_rules": hard_rules,
        },
    }
    return (
        "请严格按下面的本地视频胶囊合同制作。fixed_assets 必须直接使用；reference_assets 与 examples 仅示意，必须按本期主题重新生成，禁止照搬。不要输出胶囊解释文字，直接把合同落实到分镜、提示词、音频和质检策略中。\n"
        + json.dumps(prompt, ensure_ascii=False, indent=2)
    )
