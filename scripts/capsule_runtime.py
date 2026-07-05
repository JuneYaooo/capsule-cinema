#!/usr/bin/env python3
"""Helpers for applying active capsule packages to runtime wrapper calls."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.capsule_package_loader import (
    CapsulePackageError,
    load_assets_index,
    load_capsule_card,
    load_quality_rules,
    load_runtime_contract,
    load_stage_context,
)
from src.capsule_copywriting_contract import default_copywriting_structure_contract  # noqa: E402

SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR

ENGINE_CLASS_TO_RUNTIME = {
    "Seedance20VideoGeneratorTool": "seedance2.0",
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
    "GptImage2ProTool": "gpt-image-2-pro",
    "Gemini3ProImageGeneratorTool": "gemini3_pro",
}
IMAGE_FALLBACK_VIDEO_SENTINELS = {"none_for_default_route", "image-fallback", "image_fallback"}
STILL_IMAGE_KEN_BURNS_ROUTE = "still_images_with_ken_burns"

SPECIAL_ROUTE_CATEGORIES = {
    "action_animation",
    "action_transfer",
    "code_rendered_graphics",
    "digital_human",
    "lip_sync",
    "music_mv",
    "super_resolution",
}
BGM_ASSET_ROLES = {"bgm", "music", "audio", "background_music"}


def canonical_capsule_name(name: str) -> str:
    return str(name or "").strip()


def canonical_route_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _yaml_load(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or fallback
    except yaml.YAMLError:
        return fallback


def _package_asset_path(capsule_dir: Path, path: str) -> str:
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((capsule_dir / "assets" / path).resolve())


def _package_method(capsule_dir: Path) -> dict[str, str]:
    method: dict[str, str] = {}
    for stage in ("planning", "generation"):
        try:
            context = load_stage_context(capsule_dir, stage)
        except CapsulePackageError:
            continue
        for rel_path, text in context["files"].items():
            if not rel_path.startswith("recipes/") or not rel_path.endswith(".md"):
                continue
            key = Path(rel_path).stem
            method[key] = text
    return method


def _normalize_video_elements(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for section in ("fixed", "defaults", "user_overridable"):
        section_value = value.get(section)
        if isinstance(section_value, dict):
            normalized[section] = dict(section_value)
    forbidden = value.get("forbidden")
    if isinstance(forbidden, list):
        normalized["forbidden"] = [str(item) for item in forbidden if str(item).strip()]
    return normalized


def _flatten_video_element_config(config: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    video_elements = _normalize_video_elements(config.get("video_elements"))
    defaults = video_elements.get("defaults")
    user_overridable = video_elements.get("user_overridable")
    fixed = video_elements.get("fixed")
    if isinstance(defaults, dict):
        merged.update(defaults)
    if isinstance(user_overridable, dict):
        merged.update(user_overridable)
    if isinstance(fixed, dict):
        merged.update(fixed)
    merged.update(config)
    if video_elements:
        merged["video_elements"] = video_elements
    return merged


def _runtime_defaults_from_contract(runtime_contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults = dict(runtime_contract.get("defaults") or {}) if isinstance(runtime_contract.get("defaults"), dict) else {}
    video_elements = _normalize_video_elements(runtime_contract.get("video_elements"))
    element_defaults = video_elements.get("defaults")
    user_overridable = video_elements.get("user_overridable")
    fixed_elements = video_elements.get("fixed")
    if isinstance(element_defaults, dict):
        defaults.update(element_defaults)
    if isinstance(user_overridable, dict):
        defaults.update(user_overridable)
    if isinstance(fixed_elements, dict):
        defaults.update(fixed_elements)
    return defaults, video_elements


def load_production_contract(capsule_dir: Path) -> dict[str, Any]:
    contract = _yaml_load(capsule_dir / "contracts" / "production_contract.yaml", {})
    return contract if isinstance(contract, dict) else {}


def load_capsule_package(
    name: str,
    package_roots: list[str | Path] | None = None,
) -> dict | None:
    try:
        card = load_capsule_card(name, search_roots=package_roots)
    except CapsulePackageError:
        return None

    capsule_dir = Path(card["capsule_dir"])
    runtime_contract = load_runtime_contract(capsule_dir)
    production_contract = load_production_contract(capsule_dir)
    quality_rules = load_quality_rules(capsule_dir)
    assets = load_assets_index(capsule_dir)
    for asset in assets:
        if isinstance(asset, dict) and asset.get("path"):
            asset["path"] = _package_asset_path(capsule_dir, str(asset["path"]))

    defaults, video_elements = _runtime_defaults_from_contract(runtime_contract)
    defaults.setdefault("copywriting_structure_contract", default_copywriting_structure_contract())
    format_family = str(card.get("format_family") or card.get("category") or "").strip()
    evidence_level = str(card.get("evidence_level") or "unspecified").strip()
    production_capabilities = card.get("production_capabilities") if isinstance(card.get("production_capabilities"), list) else []
    quality_gate_profile = str(card.get("quality_gate_profile") or "").strip()
    if format_family:
        defaults.setdefault("format_family", format_family)
    if evidence_level:
        defaults.setdefault("evidence_level", evidence_level)
    if production_capabilities:
        defaults.setdefault("production_capabilities", production_capabilities)
    if quality_gate_profile:
        defaults.setdefault("quality_gate_profile", quality_gate_profile)
    input_schema = _yaml_load(capsule_dir / "contracts" / "input_schema.yaml", {})
    examples_doc = _yaml_load(capsule_dir / "examples" / "illustrative.yaml", {})
    entrypoints = card.get("entrypoints") if isinstance(card.get("entrypoints"), dict) else {}
    local_script = str(entrypoints.get("local_script") or "")
    if local_script:
        local_script = str((capsule_dir / local_script).resolve())
    config: dict[str, Any] = {
        **defaults,
        "roles": runtime_contract.get("roles", {}),
        "output_contract": runtime_contract.get("output_contract", {}),
    }
    if video_elements:
        config["video_elements"] = video_elements
    return {
        "name": canonical_capsule_name(card.get("name") or name),
        "display_name": card.get("display_name") or card.get("name") or name,
        "status": card.get("status"),
        "execution_mode": card.get("execution_mode"),
        "description": card.get("summary") or "",
        "category": card.get("category"),
        "format_family": format_family,
        "evidence_level": evidence_level,
        "production_capabilities": production_capabilities,
        "quality_gate_profile": quality_gate_profile,
        "tags": card.get("when_to_use") or [],
        "config": config,
        "method": _package_method(capsule_dir),
        "input_schema": input_schema,
        "production_contract": production_contract,
        "quality_rules": quality_rules,
        "local_assets": assets,
        "examples": examples_doc.get("examples", []) if isinstance(examples_doc, dict) else [],
        "local_script_path": local_script,
        "version": int(card.get("version") or 1),
        "capsule_dir": str(capsule_dir),
        "source_format": "package",
    }


def load_capsule_sqlite(name: str, db_path: str | Path | None) -> dict | None:
    if not db_path:
        return None
    path = Path(db_path).expanduser()
    if not path.is_file():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM capsules WHERE name = ?", (canonical_capsule_name(name),)).fetchone()
    if row is None:
        return None

    def load_json_field(field: str, fallback: Any) -> Any:
        try:
            return json.loads(row[field] or "")
        except (KeyError, TypeError, json.JSONDecodeError):
            return fallback

    config = load_json_field("config_json", {})
    if not isinstance(config, dict):
        config = {}
    config.setdefault("copywriting_structure_contract", default_copywriting_structure_contract())
    method = load_json_field("method_json", {})
    input_schema = load_json_field("input_schema_json", {})
    quality_rules = load_json_field("quality_rules_json", [])
    local_assets = load_json_field("local_assets_json", [])
    tags = load_json_field("tags_json", [])
    production_contract = config.get("production_contract") if isinstance(config.get("production_contract"), dict) else {}
    return {
        "name": canonical_capsule_name(row["name"]),
        "display_name": row["display_name"],
        "status": row["status"],
        "execution_mode": row["execution_mode"],
        "description": row["description"],
        "category": row["category"],
        "format_family": str(config.get("format_family") or row["category"] or "").strip(),
        "evidence_level": str(config.get("evidence_level") or "unspecified").strip(),
        "production_capabilities": config.get("production_capabilities") if isinstance(config.get("production_capabilities"), list) else [],
        "quality_gate_profile": str(config.get("quality_gate_profile") or "").strip(),
        "tags": tags if isinstance(tags, list) else [],
        "config": config,
        "method": method if isinstance(method, dict) else {},
        "input_schema": input_schema if isinstance(input_schema, dict) else {},
        "production_contract": production_contract,
        "quality_rules": quality_rules if isinstance(quality_rules, list) else [],
        "local_assets": local_assets if isinstance(local_assets, list) else [],
        "examples": [],
        "local_script_path": row["local_script_path"],
        "version": int(row["version"] or 1),
        "capsule_dir": "",
        "source_format": "sqlite",
    }


def load_capsule(
    name: str,
    legacy_db_path: str | Path | None = None,
    *,
    package_roots: list[str | Path] | None = None,
    prefer_package: bool = True,
) -> dict:
    requested_name = str(name or "").strip()
    if prefer_package:
        packaged = load_capsule_package(requested_name, package_roots=package_roots)
        if packaged is not None:
            return packaged
    sqlite_capsule = load_capsule_sqlite(requested_name, legacy_db_path)
    if sqlite_capsule is not None:
        return sqlite_capsule
    if not prefer_package:
        raise SystemExit(f"Capsule not found in legacy SQLite store: {requested_name}")
    raise SystemExit(f"Capsule package not found: {requested_name}; expected capsules/<name>.capsule/")


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
    raw_config = capsule.get("config") or {}
    config = _flatten_video_element_config(raw_config) if isinstance(raw_config, dict) else {}
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
    return canonical_route_key(capsule.get("category") or "") in SPECIAL_ROUTE_CATEGORIES


def production_contract_hard_rules(production_contract: dict[str, Any]) -> list[str]:
    if not isinstance(production_contract, dict) or not production_contract:
        return []
    rules = ["必须遵守 production_contract 中声明的 required_outputs、modality_contracts 和 minimum_evidence_for_release。"]
    required_outputs = production_contract.get("required_outputs")
    if isinstance(required_outputs, dict):
        required = [str(key) for key, value in required_outputs.items() if str(value) == "required"]
        if required:
            rules.append("production_contract.required_outputs 必须交付: " + ", ".join(required))
    minimum_evidence = str(production_contract.get("minimum_evidence_for_release") or "").strip()
    if minimum_evidence:
        rules.append(f"production_contract.minimum_evidence_for_release={minimum_evidence}；证据不足时必须降级声明，不能冒充完整复刻。")
    evidence_policy = production_contract.get("evidence_policy")
    if isinstance(evidence_policy, dict):
        if evidence_policy.get("metadata_only_release_allowed") is False:
            rules.append("metadata-only 只能产出内容结构草案，不能直接作为完整发布级复刻。")
        visual_level = str(evidence_policy.get("visual_claims_require") or "").strip()
        motion_audio_level = str(evidence_policy.get("motion_audio_claims_require") or "").strip()
        if visual_level:
            rules.append(f"视觉/封面/版式结论至少需要 {visual_level} 证据。")
        if motion_audio_level:
            rules.append(f"动效/节奏/配音/BGM 结论至少需要 {motion_audio_level} 证据。")
        if evidence_policy.get("l3_requires_sample_qa") is True:
            rules.append("只有生成样片并通过 QA 后，才能把胶囊标记为 L3_production_capsule。")
    return rules


def build_capsule_prompt(
    capsule: dict,
    user_requirements: str,
    user_reference_images: list[str] | None = None,
) -> str:
    raw_config = capsule.get("config") or {}
    config = _flatten_video_element_config(raw_config) if isinstance(raw_config, dict) else {}
    copywriting_structure_contract = (
        config.get("copywriting_structure_contract")
        if isinstance(config.get("copywriting_structure_contract"), dict)
        else default_copywriting_structure_contract()
    )
    method = capsule.get("method") or {}
    quality_rules = capsule.get("quality_rules") or []
    production_contract = capsule.get("production_contract") if isinstance(capsule.get("production_contract"), dict) else {}

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
        "copywriting_structure_contract": copywriting_structure_contract,
        "video_elements": config.get("video_elements"),
        "layout_strategy": config.get("layout_strategy"),
        "music_is_timing_master": config.get("music_is_timing_master"),
    }
    compact_config = {key: value for key, value in compact_config.items() if value is not None}
    fixed_assets, reference_assets = split_assets_by_reuse(capsule)
    examples = capsule.get("examples") or []
    user_reference_images = user_reference_images or []
    user_reference_summary = [
        {
            "index": index,
            "path": str(Path(path).expanduser()),
            "recommended_use": (
                "商品主图 / product_images[0] / object_reference"
                if index == 0 and capsule.get("category") == "ecommerce_product_showcase"
                else "用户参考图"
            ),
        }
        for index, path in enumerate(user_reference_images)
    ]

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
    if user_reference_summary and capsule.get("category") == "ecommerce_product_showcase":
        hard_rules.append(
            "电商胶囊收到用户参考图时，默认第 0 张就是商品主图/product_images[0]；"
            "reference_design.object_reference 必须设置 use_user_provided=true, "
            "user_provided_image_index=0，并在场景中通过 reference_type=object 或 mixed "
            "和 reference_ids 引用 object_reference/primary_objects，禁止把商品图当作普通风格图忽略。"
        )
    if capsule_requires_special_route(capsule):
        hard_rules.append("该胶囊需要专用路线；普通图生视频只能用于分镜/预览，不能冒充最终专用动作、口播同步或音乐 MV 成片。")
    if production_contract:
        hard_rules.extend(production_contract_hard_rules(production_contract))
    hard_rules.append(
        "写稿前必须按 copywriting_structure_contract 先把用户话题转成角度、前三秒、前 20 秒、完整结构、封面、标题和风险提醒。"
    )

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
            "production_contract": production_contract,
            "structure": lines_from("structure"),
            "routing_rules": lines_from("routing_rules"),
            "prompt_rules": lines_from("prompt_rules"),
            "style_rules": lines_from("style_rules"),
            "copy_rules": lines_from("copy_rules"),
            "fixed_assets": fixed_assets,
            "reference_assets": reference_assets,
            "user_reference_images": user_reference_summary,
            "examples": examples,
            "quality_rules": [
                {"id": item.get("id"), "rule": item.get("rule"), "severity": item.get("severity")}
                for item in quality_rules
                if isinstance(item, dict)
            ],
            "hard_runtime_rules": hard_rules,
        },
    }
    reference_block = ""
    if user_reference_summary:
        reference_lines = [
            "【用户提供的参考图片】",
            *[
                f"【参考图{item['index']}】path={item['path']}；推荐用途：{item['recommended_use']}"
                for item in user_reference_summary
            ],
        ]
        if capsule.get("category") == "ecommerce_product_showcase":
            reference_lines.append(
                "本次为电商商品视频：参考图0必须作为商品外观身份锚点，不得仅作为风格参考。"
            )
        reference_block = "\n" + "\n".join(reference_lines) + "\n"
    return (
        "请严格按下面的本地视频胶囊合同制作。fixed_assets 必须直接使用；reference_assets 与 examples 仅示意，必须按本期主题重新生成，禁止照搬。不要输出胶囊解释文字，直接把合同落实到分镜、提示词、音频和质检策略中。\n"
        + reference_block
        + json.dumps(prompt, ensure_ascii=False, indent=2)
    )
