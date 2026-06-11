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
REPO_ROOT = SKILL_DIR.parent

DEFAULT_DB_CANDIDATES = [
    lambda: os.environ.get("VIDEO_CAPSULE_DB"),
    lambda: os.environ.get("VIDEO_PRODUCTION_CAPSULE_DB"),
    lambda: str(REPO_ROOT / "artifacts" / "capsules" / "initial_capsules.sqlite"),
    lambda: str(Path.home() / ".codex" / "video-production" / "capsules.sqlite"),
]

ENGINE_CLASS_TO_RUNTIME = {
    "SeedanceVideoGeneratorTool": "seedance",
    "SeedanceFastVideoGeneratorTool": "seedance",
    "Jimeng35ProVideoGeneratorTool": "jimeng35pro",
    "Veo3VideoGeneratorTool": "veo3",
    "GrokVideoGeneratorTool": "grok",
}

SPECIAL_ROUTE_CATEGORIES = {"action_transfer", "digital_human", "music_mv"}


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
    path = resolve_capsule_db(db_path)
    if not path.exists():
        raise SystemExit(f"Capsule DB not found: {path}")
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM capsules WHERE name = ?", (name,)).fetchone()
    if not row:
        raise SystemExit(f"Capsule not found: {name} in {path}")
    payload = {
        "name": row["name"],
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
        "local_script_path": row["local_script_path"],
        "version": int(row["version"] or 1),
        "db_path": str(path),
    }
    return payload


def capsule_runtime_defaults(capsule: dict) -> dict:
    config = capsule.get("config") or {}
    defaults: dict[str, Any] = {}
    if config.get("aspect_ratio"):
        defaults["aspect_ratio"] = config["aspect_ratio"]
    if "add_subtitles" in config:
        defaults["add_subtitles"] = bool(config["add_subtitles"])
    if "add_background_music" in config:
        defaults["add_background_music"] = bool(config["add_background_music"])
    if config.get("bgm_volume") is not None:
        defaults["bgm_volume"] = config["bgm_volume"]
    if config.get("voice_volume") is not None:
        defaults["voice_volume"] = config["voice_volume"]
    runtime_engine = ENGINE_CLASS_TO_RUNTIME.get(config.get("video_engine", ""))
    if runtime_engine:
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

    hard_rules = []
    if config.get("has_narration") is False:
        hard_rules.append("默认不要旁白，不要生成 TTS 配音；除非用户显式要求旁白。")
    if config.get("add_subtitles") is False:
        hard_rules.append("默认不要字幕；不要为了模板自动加字幕。")
    if config.get("add_background_music") is False:
        hard_rules.append("默认不要额外背景音乐；如果是 MV，音乐本身是主音频。")
    if config.get("has_narration") is True:
        hard_rules.append("旁白视频必须以 TTS 实际时长为时间基准，画面不能短于或长于旁白形成冻结尾巴或静音尾巴。")
    if capsule_requires_special_route(capsule):
        hard_rules.append("该胶囊需要专用路线；普通图生视频只能用于分镜/预览，不能冒充最终专用动作、口播同步或音乐 MV 成片。")

    prompt = {
        "user_requirements": user_requirements,
        "capsule": {
            "name": capsule.get("name"),
            "display_name": capsule.get("display_name"),
            "category": capsule.get("category"),
            "description": capsule.get("description"),
            "config": compact_config,
            "structure": lines_from("structure"),
            "routing_rules": lines_from("routing_rules"),
            "prompt_rules": lines_from("prompt_rules"),
            "style_rules": lines_from("style_rules"),
            "copy_rules": lines_from("copy_rules"),
            "quality_rules": [
                {"id": item.get("id"), "rule": item.get("rule"), "severity": item.get("severity")}
                for item in quality_rules
                if isinstance(item, dict)
            ],
            "hard_runtime_rules": hard_rules,
        },
    }
    return (
        "请严格按下面的本地视频胶囊合同制作。不要输出胶囊解释文字，直接把合同落实到分镜、提示词、音频和质检策略中。\n"
        + json.dumps(prompt, ensure_ascii=False, indent=2)
    )
