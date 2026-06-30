#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAMES = [
    "repo_showcase",
    "life_sim",
    "felt_asmr",
    "guofeng_history",
    "ecommerce_product_showcase",
    "art_motion",
]

STRUCTURE_KEYS = {"structure", "story_formula", "opening", "script_skeleton", "execution_rules"}
VISUAL_KEYS = {"visual_rules", "prompt_contract", "style_rules", "visual_grammar", "continuity_system"}
MOTION_KEYS = {"motion_rules", "generation_workflow", "video_rules", "content_aware_motion_policy"}
AUDIO_KEYS = {"audio_rules", "bgm_rules", "tts_rules", "music_policy"}
SUBTITLE_KEYS = {"subtitle_rules", "bottom_card_rules", "text_layout_rules", "five_line_bottom_cards_policy"}
COPY_KEYS = {"copy_rules", "platform_guidance", "hook_and_title", "copy_policy"}
REPAIR_KEYS = {"repair_playbook", "known_pitfalls", "failure_modes_and_repairs"}
DEFAULT_MIN_FREE_BYTES = 500 * 1024 * 1024
EPHEMERAL_ASSET_ROLES = {"qa_report", "prompt_snapshot", "final_artifact", "final_video", "evidence"}
EPHEMERAL_ASSET_REUSE = {"evidence_only", "deliverable", "final_only"}
EPHEMERAL_ASSET_HINTS = {
    "qa",
    "report",
    "prompt",
    "snapshot",
    "final",
    "artifact",
    "deliverable",
    "evidence",
    "output",
}
FORBIDDEN_RECIPE_TEXT = (
    ("artifact_manifest.json", "publishing manifest"),
    ("feedback_json", "legacy feedback export"),
    ("run_history", "legacy run evidence"),
)
OUTPUT_PATH_TEXT = re.compile(r"(?i)(?:^|[\s'\"(])(?:[^\s'\"()]*/)?output(?:/[^\s'\"()]*)?")


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _dump_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _ensure_free_space(
    path: str | Path,
    minimum_bytes: int = DEFAULT_MIN_FREE_BYTES,
    disk_usage: Any = shutil.disk_usage,
) -> None:
    target = Path(path).expanduser()
    probe = target if target.exists() else target.parent
    total, used, free = disk_usage(probe)
    del total, used
    if free < minimum_bytes:
        raise SystemExit(
            f"insufficient free disk space for v3 conversion: need at least {minimum_bytes} bytes free, found {free}"
        )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def load_capsule_from_db(db_path: str | Path, name: str) -> dict | None:
    path = Path(db_path).expanduser()
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        columns = _table_columns(conn, "capsules")
        row = conn.execute("SELECT * FROM capsules WHERE name = ?", (name,)).fetchone()
        if not row:
            return None

        def col(key: str, default: Any = "") -> Any:
            return row[key] if key in columns else default

        return {
            "name": row["name"],
            "display_name": col("display_name", row["name"]),
            "status": col("status", "draft"),
            "execution_mode": col("execution_mode", "preset"),
            "description": col("description", ""),
            "category": col("category", ""),
            "tags": _json_load(col("tags_json", "[]"), []),
            "config": _json_load(col("config_json", "{}"), {}),
            "method": _json_load(col("method_json", "{}"), {}),
            "input_schema": _json_load(col("input_schema_json", "{}"), {}),
            "quality_rules": _json_load(col("quality_rules_json", "[]"), []),
            "local_assets": _json_load(col("local_assets_json", "[]"), []),
            "examples": _json_load(col("examples_json", "[]"), []),
            "local_script_path": col("local_script_path", ""),
            "version": int(col("version", 1) or 1),
            "run_history": _json_load(col("run_history_json", "[]"), []),
            "feedback": _json_load(col("feedback_json", "[]"), []),
            "changelog": _json_load(col("changelog_json", "[]"), []),
            "notes": col("notes", ""),
            "source": {
                "type": "sqlite",
                "db_path": str(path),
                "legacy_version": int(col("version", 1) or 1),
            },
        }


def load_capsule_from_zip_dir(zip_dir: str | Path, name: str) -> dict | None:
    package = Path(zip_dir).expanduser() / f"{name}.capsule.zip"
    if not package.is_file():
        return None
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    capsule = manifest.get("capsule")
    if not isinstance(capsule, dict):
        return None
    capsule = dict(capsule)
    capsule.setdefault("run_history", [])
    capsule.setdefault("feedback", [])
    capsule.setdefault("changelog", [])
    capsule["source"] = {
        "type": "zip",
        "package": str(package),
        "legacy_version": capsule.get("version", 1),
    }
    return capsule


def _runtime_contract(config: dict) -> dict:
    runtime = {
        "roles": config.get("roles") if isinstance(config.get("roles"), dict) else {},
        "output_contract": config.get("output_contract") if isinstance(config.get("output_contract"), dict) else {},
        "defaults": {},
    }
    default_keys = [
        "aspect_ratio",
        "aspect_ratio_options",
        "target_duration",
        "target_duration_range",
        "target_duration_max",
        "bgm_volume",
        "voice_volume",
        "subtitle_max_chars",
        "generated_scene_count_range",
        "final_micro_shot_count_range",
        "micro_shot_duration_seconds",
        "visual_generation_type",
        "static_fallback_can_pass_release",
        "static_zoompan_fallback_preview_only",
        "require_real_motion_video_segments",
    ]
    runtime["defaults"] = {key: config[key] for key in default_keys if key in config}
    return runtime


def _sanitize_recipe_text(text: str) -> str:
    sanitized = text
    for needle, replacement in FORBIDDEN_RECIPE_TEXT:
        sanitized = sanitized.replace(needle, replacement)
    sanitized = OUTPUT_PATH_TEXT.sub(" [final artifact path omitted]", sanitized).strip()
    return sanitized


def _sanitize_recipe_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_recipe_text(value)
    if isinstance(value, list):
        return [_sanitize_recipe_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_recipe_value(item) for key, item in value.items()}
    return value


def _format_value(value: Any) -> str:
    sanitized = _sanitize_recipe_value(value)
    if isinstance(sanitized, str):
        return sanitized
    return json.dumps(sanitized, ensure_ascii=False, indent=2)


def _portable_source_metadata(source: dict[str, Any], legacy_version: int) -> dict[str, Any]:
    portable: dict[str, Any] = {}
    source_type = source.get("type")
    if isinstance(source_type, str) and source_type.strip():
        portable["type"] = source_type
    portable["legacy_version"] = legacy_version
    portable["converted_at"] = datetime.now(timezone.utc).isoformat()
    return portable


def _recipe_markdown(title: str, items: dict[str, Any]) -> str:
    if not items:
        return f"# {title}\n\nNo capsule-specific rules were migrated for this section.\n"
    lines = [f"# {title}", ""]
    for key, value in items.items():
        lines.append(f"## {key}")
        lines.append("")
        if isinstance(value, list):
            for item in value:
                lines.append(f"- {_format_value(item)}")
        else:
            lines.append(_format_value(value))
        lines.append("")
    return "\n".join(lines)


def _split_method(method: dict) -> dict[str, dict[str, Any]]:
    sections = {
        "structure": {},
        "visual": {},
        "motion": {},
        "audio": {},
        "subtitle": {},
        "copy": {},
        "repair_playbook": {},
        "legacy_notes": {},
    }
    buckets = [
        ("structure", STRUCTURE_KEYS),
        ("visual", VISUAL_KEYS),
        ("motion", MOTION_KEYS),
        ("audio", AUDIO_KEYS),
        ("subtitle", SUBTITLE_KEYS),
        ("copy", COPY_KEYS),
        ("repair_playbook", REPAIR_KEYS),
    ]
    for key, value in (method or {}).items():
        target = "legacy_notes"
        for section, keys in buckets:
            if key in keys:
                target = section
                break
        sections[target][key] = value
    return sections


def _safe_asset_entry(asset: dict) -> dict:
    return {
        "key": asset.get("key") or asset.get("name") or "",
        "role": asset.get("role") or asset.get("type") or "asset",
        "reuse": asset.get("reuse") or "reference_only",
        "path": Path(str(asset.get("path") or "")).name if asset.get("path") else "",
        "description": asset.get("description") or "",
        "tags": asset.get("tags") or [],
    }


def _should_include_asset(asset: dict) -> bool:
    role = str(asset.get("role") or asset.get("type") or "").lower()
    reuse = str(asset.get("reuse") or "").lower()
    raw_path = str(asset.get("path") or "")
    source = Path(raw_path).expanduser()
    tokens = {
        role,
        reuse,
        str(asset.get("key") or "").lower(),
        source.name.lower(),
        *{part.lower() for part in source.parts},
    }
    if role in EPHEMERAL_ASSET_ROLES or reuse in EPHEMERAL_ASSET_REUSE:
        return False
    return not any(hint in token for token in tokens for hint in EPHEMERAL_ASSET_HINTS)


def _copy_asset_files(capsule_dir: Path, local_assets: list[dict]) -> list[dict]:
    converted = []
    for asset in local_assets or []:
        if not isinstance(asset, dict):
            continue
        if not _should_include_asset(asset):
            continue
        entry = _safe_asset_entry(asset)
        raw_path = str(asset.get("path") or "")
        if raw_path and Path(raw_path).expanduser().is_file() and "output" not in Path(raw_path).parts:
            source = Path(raw_path).expanduser()
            dest_name = f"{entry['key']}__{source.name}" if entry["key"] else source.name
            dest = capsule_dir / "assets" / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            entry["path"] = dest.name
        converted.append(entry)
    return converted


def _card_markdown(payload: dict) -> str:
    when = payload.get("tags") or []
    lines = [
        f"# {payload.get('display_name') or payload.get('name')}",
        "",
        "## Purpose",
        "",
        payload.get("description") or "Reusable Capsule Cinema recipe.",
        "",
        "## When To Use",
        "",
    ]
    lines.extend([f"- {item}" for item in when] or ["- Use when the user explicitly selects this capsule."])
    lines.extend(
        [
            "",
            "## When Not To Use",
            "",
            "- Do not use when the requested output conflicts with the runtime contract.",
            "- Do not copy illustrative examples as final content.",
            "",
            "## Stage Reading",
            "",
            "- Routing: read `capsule.yaml` and this card.",
            "- Planning: read the recipe files named under `read_order.planning`.",
            "- Generation: read the runtime contract, motion recipe, and asset index.",
            "- QA: read the quality rules and release gates.",
            "- Learning: read promoted lessons only; raw evidence is local-only.",
        ]
    )
    return "\n".join(lines)


def convert_capsule(
    payload: dict,
    output_root: str | Path,
    include_evidence: bool = False,
    overwrite: bool = False,
) -> Path:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise SystemExit("capsule payload missing name")
    out_root = Path(output_root).expanduser()
    cap_dir = out_root / f"{name}.capsule"
    if cap_dir.exists():
        if not overwrite:
            raise SystemExit(f"v3 capsule already exists: {cap_dir}")
        shutil.rmtree(cap_dir)
    _ensure_free_space(out_root)
    cap_dir.mkdir(parents=True, exist_ok=True)

    config = payload.get("config") or {}
    method = payload.get("method") or {}
    runtime = _runtime_contract(config)
    source = _portable_source_metadata(
        dict(payload.get("source") or {}),
        int(payload.get("version") or 1),
    )

    read_order = {
        "routing": ["CARD.md", "contracts/runtime.yaml"],
        "planning": ["recipes/structure.md", "recipes/visual.md", "recipes/audio.md", "recipes/copy.md"],
        "generation": ["contracts/runtime.yaml", "recipes/motion.md", "assets/index.yaml"],
        "qa": ["quality/rules.yaml", "quality/release_gates.yaml"],
        "learning": ["learning/promoted_lessons.yaml"],
    }
    entrypoints = {"preset": "general_video"}
    local_script_path = str(payload.get("local_script_path") or "")
    if payload.get("execution_mode") == "local_script" and local_script_path:
        script_source = Path(local_script_path).expanduser()
        if script_source.is_file():
            script_dest = cap_dir / "scripts" / script_source.name
            script_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(script_source, script_dest)
            entrypoints["local_script"] = f"scripts/{script_source.name}"
        else:
            entrypoints["local_script"] = local_script_path

    _dump_yaml(
        cap_dir / "capsule.yaml",
        {
            "schema_version": "capsule.v3",
            "name": name,
            "display_name": payload.get("display_name") or name,
            "version": int(payload.get("version") or 1),
            "status": payload.get("status") or "draft",
            "execution_mode": payload.get("execution_mode") or "preset",
            "category": payload.get("category") or "",
            "summary": payload.get("description") or "",
            "when_to_use": payload.get("tags") or [],
            "when_not_to_use": [],
            "read_order": read_order,
            "entrypoints": entrypoints,
            "source": source,
        },
    )
    _write_text(cap_dir / "CARD.md", _card_markdown(payload))
    _dump_yaml(cap_dir / "contracts" / "runtime.yaml", runtime)
    _dump_yaml(cap_dir / "contracts" / "input_schema.yaml", {"fields": payload.get("input_schema") or {}})

    sections = _split_method(method)
    for section, items in sections.items():
        if section == "legacy_notes" and not items:
            continue
        _write_text(cap_dir / "recipes" / f"{section}.md", _recipe_markdown(section.replace("_", " ").title(), items))

    _dump_yaml(cap_dir / "quality" / "rules.yaml", {"rules": payload.get("quality_rules") or []})
    _dump_yaml(
        cap_dir / "quality" / "release_gates.yaml",
        {
            "gates": [
                item.get("id")
                for item in payload.get("quality_rules") or []
                if isinstance(item, dict) and item.get("id")
            ]
        },
    )
    _dump_yaml(cap_dir / "assets" / "index.yaml", {"assets": _copy_asset_files(cap_dir, payload.get("local_assets") or [])})
    _dump_yaml(cap_dir / "examples" / "illustrative.yaml", {"examples": payload.get("examples") or []})
    _dump_yaml(cap_dir / "learning" / "promoted_lessons.yaml", {"lessons": []})

    if include_evidence:
        evidence = out_root / "_legacy_evidence" / name
        _dump_json(evidence / "run_history.json", payload.get("run_history") or [])
        _dump_json(evidence / "feedback.json", payload.get("feedback") or [])
        _dump_json(evidence / "changelog.json", payload.get("changelog") or [])
        _dump_yaml(evidence / "lesson_candidates.yaml", {"candidates": []})
    return cap_dir


def _names_arg(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert v2 SQLite/zip capsules to v3 package directories.")
    parser.add_argument("--from-db", default="")
    parser.add_argument("--from-zip-dir", default="capsules")
    parser.add_argument("--names", default=",".join(DEFAULT_NAMES))
    parser.add_argument("--out", default="capsules_v3")
    parser.add_argument("--include-evidence", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    converted = []
    for name in _names_arg(args.names):
        payload = load_capsule_from_db(args.from_db, name) if args.from_db else None
        if payload is None:
            payload = load_capsule_from_zip_dir(args.from_zip_dir, name)
        if payload is None:
            raise SystemExit(f"capsule not found in db or zip dir: {name}")
        converted.append(
            str(
                convert_capsule(
                    payload,
                    out,
                    include_evidence=args.include_evidence,
                    overwrite=args.overwrite,
                )
            )
        )
    print(json.dumps({"converted": converted}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
