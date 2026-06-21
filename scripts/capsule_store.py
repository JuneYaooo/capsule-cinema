#!/usr/bin/env python3
"""Single-user local SQLite capsule store for video-production."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_DB = Path.home() / ".codex" / "video-production" / "capsules.sqlite"
SCHEMA_VERSION = "single-user-1.0"
STATUSES = {"draft", "active", "archived", "disabled"}
STATUS_ALIASES = {
    "validated": "active",
    "scale_ready": "active",
    "SCALE_READY": "active",
    "suspended": "archived",
}
EXECUTION_MODES = {"preset", "local_script"}

DEFAULT_CONFIG = {
    "aspect_ratio": "9:16",
    "target_duration": 30,
    "target_duration_max": 180,
    "tts_provider": "minimax",
    "tts_speed": 1.2,
    "tts_volume": 2.0,
    "voice_volume": 1.5,
    "bgm_volume": 0.08,
    "image_engine": "GptImage2Tool",
    "video_engine": "SeedanceFastVideoGeneratorTool",
    "subtitle_max_chars": 14,
    "trim_gap": 0.3,
    "has_narration": True,
    "add_subtitles": True,
    "add_background_music": True,
}

ENGINE_ALIASES = {
    "seedream5": "Seedream5ImageGeneratorTool",
    "gemini3_pro": "Gemini3ProImageGeneratorTool",
    "gpt-image-2": "GptImage2Tool",
    "gpt_image2": "GptImage2Tool",
    "gpt-image2": "GptImage2Tool",
    "jimeng35pro": "Jimeng35ProVideoGeneratorTool",
    "jimeng3.5pro": "Jimeng35ProVideoGeneratorTool",
    "seedance": "SeedanceVideoGeneratorTool",
    "seedance-fast": "SeedanceFastVideoGeneratorTool",
    "seedance-1.0-fast": "SeedanceFastVideoGeneratorTool",
    "veo3": "Veo3VideoGeneratorTool",
    "grok": "GrokVideoGeneratorTool",
    "grok_video": "GrokVideoGeneratorTool",
}

SECRET_PATTERNS = [
    re.compile(r"bearer\s+[A-Za-z0-9._-]+", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
]
SECRET_KEY_PATTERNS = [
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"access[_-]?token", re.I),
    re.compile(r"authorization", re.I),
    re.compile(r"cookie", re.I),
    re.compile(r"secret", re.I),
]
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
REMOTE_VALUE_PATTERN = re.compile(r"^(https?://|s3://|oss://|qiniu://)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def db_path() -> Path:
    return Path(
        os.environ.get("VIDEO_CAPSULE_DB")
        or os.environ.get("VIDEO_PRODUCTION_CAPSULE_DB")
        or DEFAULT_DB
    ).expanduser()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def parse_json(raw: str | None, label: str, expected: type | tuple[type, ...], default: Any) -> Any:
    if raw is None:
        return default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, expected):
        if isinstance(expected, tuple):
            expected_name = ", ".join(item.__name__ for item in expected)
        else:
            expected_name = expected.__name__
        raise SystemExit(f"{label} must be {expected_name}")
    return value


def parse_tags(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = STATUS_ALIASES.get(value, value).lower()
    if normalized not in STATUSES:
        raise SystemExit(f"Unknown status '{value}'. Allowed: {', '.join(sorted(STATUSES))}")
    return normalized


def normalize_execution_mode(value: str | None, *, local_script_path: str = "") -> str | None:
    if value is None:
        return "local_script" if local_script_path else None
    if value == "script_package":
        return "local_script"
    if value not in EXECUTION_MODES:
        raise SystemExit(f"Unknown execution mode '{value}'. Allowed: {', '.join(sorted(EXECUTION_MODES))}")
    return value


def table_columns(conn: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row["name"]: row for row in rows}


def ensure_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS capsules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            execution_mode TEXT NOT NULL DEFAULT 'preset',
            description TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            config_json TEXT NOT NULL DEFAULT '{}',
            method_json TEXT NOT NULL DEFAULT '{}',
            input_schema_json TEXT NOT NULL DEFAULT '{}',
            quality_rules_json TEXT NOT NULL DEFAULT '[]',
            local_assets_json TEXT NOT NULL DEFAULT '[]',
            local_script_path TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            run_history_json TEXT NOT NULL DEFAULT '[]',
            feedback_json TEXT NOT NULL DEFAULT '[]',
            changelog_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    for name, ddl in {
        "display_name": "TEXT NOT NULL DEFAULT ''",
        "execution_mode": "TEXT NOT NULL DEFAULT 'preset'",
        "description": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT NOT NULL DEFAULT ''",
        "tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "config_json": "TEXT NOT NULL DEFAULT '{}'",
        "method_json": "TEXT NOT NULL DEFAULT '{}'",
        "input_schema_json": "TEXT NOT NULL DEFAULT '{}'",
        "quality_rules_json": "TEXT NOT NULL DEFAULT '[]'",
        "local_assets_json": "TEXT NOT NULL DEFAULT '[]'",
        "local_script_path": "TEXT NOT NULL DEFAULT ''",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "run_history_json": "TEXT NOT NULL DEFAULT '[]'",
        "feedback_json": "TEXT NOT NULL DEFAULT '[]'",
        "changelog_json": "TEXT NOT NULL DEFAULT '[]'",
        "notes": "TEXT NOT NULL DEFAULT ''",
    }.items():
        ensure_column(conn, "capsules", name, ddl)
    migrate_legacy_rows(conn)
    conn.commit()


def normalize_engine_name(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return ENGINE_ALIASES.get(value, value)


def normalize_config(config: dict | None) -> dict:
    merged = {**DEFAULT_CONFIG, **(config or {})}
    if "bgm" in merged and "bgm_path" not in merged:
        merged["bgm_path"] = merged["bgm"]
    if "has_subtitle" in merged and "add_subtitles" not in merged:
        merged["add_subtitles"] = bool(merged["has_subtitle"])
    if "has_bgm" in merged and "add_background_music" not in merged:
        merged["add_background_music"] = bool(merged["has_bgm"])
    for key in ("image_engine", "video_engine"):
        if key in merged:
            merged[key] = normalize_engine_name(merged[key])
    return merged


def default_input_schema(config: dict) -> dict:
    return {
        "topic": {"type": "string", "required": True},
        "aspect_ratio": {
            "type": "string",
            "required": False,
            "default": config.get("aspect_ratio", "9:16"),
            "enum": ["9:16", "16:9", "1:1", "4:5"],
        },
        "target_duration": {
            "type": "integer",
            "required": False,
            "default": config.get("target_duration", 30),
            "maximum": config.get("target_duration_max", 180),
        },
    }


def default_quality_rules(config: dict) -> list[dict]:
    rules: list[dict] = [
        {"id": "final_video_required", "type": "artifact_required", "category": "final_video"},
        {"id": "manifest_required", "type": "manifest_required"},
        {
            "id": "final_video_media_quality",
            "type": "video_quality",
            "category": "final_video",
            "expected_aspect_ratio": config.get("aspect_ratio"),
            "min_duration_seconds": 6.0,
            "require_audio": bool(config.get("has_narration", True) or config.get("add_background_music", True)),
        },
    ]
    for key in ("aspect_ratio", "image_engine", "video_engine"):
        if config.get(key):
            rules.append({"id": f"{key}_locked", "type": "param_equals", "key": key, "value": config[key]})
    if config.get("add_subtitles"):
        rules.append({"id": "subtitle_expected", "type": "artifact_recommended", "category": "subtitle"})
    if config.get("add_background_music"):
        rules.append({"id": "bgm_expected", "type": "artifact_recommended", "category": "bgm"})
    return rules


def normalize_local_assets(raw: Any) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, dict):
        if raw and all(isinstance(value, list) for value in raw.values()):
            items = [item for group in raw.values() for item in (group or [])]
        else:
            items = [{"key": key, **value} for key, value in raw.items() if isinstance(value, dict)]
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    normalized: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or item.get("local_path")
        if not path and item.get("url") and not REMOTE_VALUE_PATTERN.search(str(item["url"])):
            path = item["url"]
        entry = {
            "key": item.get("key") or item.get("name") or item.get("label") or "",
            "role": item.get("role") or item.get("type") or "asset",
            "path": str(path or ""),
            "description": item.get("description") or item.get("label") or "",
            "tags": item.get("tags") or [],
        }
        normalized.append(entry)
    return normalized


def legacy_local_script_path(config: dict, assets: list[dict], current: str = "") -> str:
    if current:
        return current
    for key in ("local_script_path", "script_path", "script_package_ref", "script_package_key"):
        value = config.get(key)
        if isinstance(value, str) and value and not REMOTE_VALUE_PATTERN.search(value):
            return value
    for item in assets:
        if item.get("role") in {"local_script", "script_package"} and item.get("path"):
            return str(item["path"])
    return ""


def migrate_legacy_rows(conn: sqlite3.Connection) -> None:
    columns = table_columns(conn, "capsules")
    rows = conn.execute("SELECT * FROM capsules").fetchall()
    for row in rows:
        status = normalize_status(row["status"]) if row["status"] else "draft"
        config = json_load(row["config_json"] if "config_json" in columns else None, {})
        legacy_capsule_config = json_load(row["capsule_config_json"] if "capsule_config_json" in columns else None, {})
        legacy_defaults = json_load(row["default_params_json"] if "default_params_json" in columns else None, {})
        config = normalize_config({**legacy_capsule_config, **legacy_defaults, **config})

        assets_raw = json_load(row["local_assets_json"] if "local_assets_json" in columns else None, None)
        if assets_raw is None:
            assets_raw = json_load(row["assets_json"] if "assets_json" in columns else None, [])
        local_assets = normalize_local_assets(assets_raw)

        local_script_path = row["local_script_path"] if "local_script_path" in columns else ""
        legacy_script_ref = row["script_package_ref"] if "script_package_ref" in columns else ""
        if legacy_script_ref and not REMOTE_VALUE_PATTERN.search(legacy_script_ref):
            local_script_path = local_script_path or legacy_script_ref
        local_script_path = legacy_local_script_path(config, local_assets, local_script_path)

        execution_mode = row["execution_mode"] if "execution_mode" in columns else ""
        if execution_mode not in EXECUTION_MODES:
            execution_mode = ""
        legacy_mode = row["mode"] if "mode" in columns else ""
        if legacy_mode in EXECUTION_MODES and (not execution_mode or (execution_mode == "preset" and legacy_mode != "preset")):
            execution_mode = legacy_mode
        execution_mode = normalize_execution_mode(execution_mode, local_script_path=local_script_path) or "preset"

        input_schema = json_load(row["input_schema_json"] if "input_schema_json" in columns else None, {}) or default_input_schema(config)
        quality_rules = json_load(row["quality_rules_json"] if "quality_rules_json" in columns else None, []) or default_quality_rules(config)
        method = json_load(row["method_json"] if "method_json" in columns else None, {})
        run_history = json_load(row["run_history_json"] if "run_history_json" in columns else None, [])
        feedback = json_load(row["feedback_json"] if "feedback_json" in columns else None, [])
        changelog = json_load(row["changelog_json"] if "changelog_json" in columns else None, [])

        conn.execute(
            """
            UPDATE capsules
            SET status = ?, execution_mode = ?, config_json = ?, input_schema_json = ?,
                quality_rules_json = ?, local_assets_json = ?, local_script_path = ?,
                method_json = ?, run_history_json = ?, feedback_json = ?, changelog_json = ?
            WHERE id = ?
            """,
            (
                status,
                execution_mode,
                json_dump(config),
                json_dump(input_schema),
                json_dump(quality_rules),
                json_dump(local_assets),
                local_script_path,
                json_dump(method),
                json_dump(run_history),
                json_dump(feedback),
                json_dump(changelog),
                row["id"],
            ),
        )


def get_capsule(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM capsules WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise SystemExit(f"Capsule not found: {name}")
    return row


def read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def manifest_final_video(manifest: dict) -> str:
    for item in manifest.get("artifacts", []):
        if isinstance(item, dict) and item.get("category") == "final_video" and item.get("path"):
            return str(item["path"])
    return ""


def build_contract(row: sqlite3.Row) -> dict:
    config = normalize_config(json_load(row["config_json"], {}))
    input_schema = json_load(row["input_schema_json"], {}) or default_input_schema(config)
    quality_rules = json_load(row["quality_rules_json"], []) or default_quality_rules(config)
    return {
        "schema_version": SCHEMA_VERSION,
        "capsule_name": row["name"],
        "version": int(row["version"] or 1),
        "execution_mode": row["execution_mode"],
        "local_script_path": row["local_script_path"],
        "config": config,
        "method": json_load(row["method_json"], {}),
        "input_schema": input_schema,
        "quality_rules": quality_rules,
        "local_assets": normalize_local_assets(json_load(row["local_assets_json"], [])),
    }


def upsert(args: argparse.Namespace) -> None:
    status = normalize_status(args.status)
    config_patch = parse_json(args.config_json, "--config-json", dict, {})
    method_patch = parse_json(args.method_json, "--method-json", dict, {})
    input_schema = parse_json(args.input_schema_json, "--input-schema-json", dict, None)
    quality_rules = parse_json(args.quality_rules_json, "--quality-rules-json", list, None)
    local_assets = parse_json(args.local_assets_json, "--local-assets-json", (list, dict), None)
    tags = parse_tags(args.tags)

    with connect() as conn:
        init_db(conn)
        existing = conn.execute("SELECT * FROM capsules WHERE name = ?", (args.name,)).fetchone()
        if existing:
            replace_existing = bool(getattr(args, "replace_existing", False))
            config = config_patch if replace_existing else {**json_load(existing["config_json"], {}), **config_patch}
            method = method_patch if replace_existing else {**json_load(existing["method_json"], {}), **method_patch}
            local_script_path = args.local_script_path if args.local_script_path is not None else existing["local_script_path"]
            version = int(existing["version"] or 1) + (1 if args.bump_version else 0)
            values = {
                "id": existing["id"],
                "display_name": args.display_name if args.display_name is not None else existing["display_name"],
                "status": status or existing["status"],
                "execution_mode": normalize_execution_mode(args.execution_mode, local_script_path=local_script_path) or existing["execution_mode"],
                "description": args.description if args.description is not None else existing["description"],
                "category": args.category if args.category is not None else existing["category"],
                "tags": tags if tags is not None else json_load(existing["tags_json"], []),
                "config": normalize_config(config),
                "method": method,
                "input_schema": input_schema if input_schema is not None else json_load(existing["input_schema_json"], {}),
                "quality_rules": quality_rules if quality_rules is not None else json_load(existing["quality_rules_json"], []),
                "local_assets": normalize_local_assets(local_assets if local_assets is not None else json_load(existing["local_assets_json"], [])),
                "local_script_path": local_script_path,
                "version": version,
                "run_history": json_load(existing["run_history_json"], []),
                "feedback": json_load(existing["feedback_json"], []),
                "changelog": json_load(existing["changelog_json"], []),
                "notes": args.notes if args.notes is not None else existing["notes"],
                "created_at": existing["created_at"],
            }
        else:
            local_script_path = args.local_script_path or ""
            config = normalize_config(config_patch)
            values = {
                "id": new_id(),
                "display_name": args.display_name or "",
                "status": status or "draft",
                "execution_mode": normalize_execution_mode(args.execution_mode, local_script_path=local_script_path) or "preset",
                "description": args.description or "",
                "category": args.category or "",
                "tags": tags or [],
                "config": config,
                "method": method_patch,
                "input_schema": input_schema or default_input_schema(config),
                "quality_rules": quality_rules or default_quality_rules(config),
                "local_assets": normalize_local_assets(local_assets or []),
                "local_script_path": local_script_path,
                "version": 1,
                "run_history": [],
                "feedback": [],
                "changelog": [],
                "notes": args.notes or "",
                "created_at": now(),
            }

        if args.bump_version or not existing:
            values["changelog"].append({
                "version": values["version"],
                "at": now(),
                "source": args.change_source,
                "text": args.changelog,
            })

        ts = now()
        id_value = values["id"]
        id_column = table_columns(conn, "capsules").get("id")
        if not existing and id_column and "INT" in str(id_column["type"]).upper():
            id_value = None
        conn.execute(
            """
            INSERT INTO capsules (
                id, name, display_name, status, execution_mode, description, category,
                tags_json, config_json, method_json, input_schema_json, quality_rules_json,
                local_assets_json, local_script_path, version, run_history_json,
                feedback_json, changelog_json, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                display_name = excluded.display_name,
                status = excluded.status,
                execution_mode = excluded.execution_mode,
                description = excluded.description,
                category = excluded.category,
                tags_json = excluded.tags_json,
                config_json = excluded.config_json,
                method_json = excluded.method_json,
                input_schema_json = excluded.input_schema_json,
                quality_rules_json = excluded.quality_rules_json,
                local_assets_json = excluded.local_assets_json,
                local_script_path = excluded.local_script_path,
                version = excluded.version,
                run_history_json = excluded.run_history_json,
                feedback_json = excluded.feedback_json,
                changelog_json = excluded.changelog_json,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                id_value,
                args.name,
                values["display_name"],
                values["status"],
                values["execution_mode"],
                values["description"],
                values["category"],
                json_dump(values["tags"]),
                json_dump(values["config"]),
                json_dump(values["method"]),
                json_dump(values["input_schema"]),
                json_dump(values["quality_rules"]),
                json_dump(values["local_assets"]),
                values["local_script_path"],
                values["version"],
                json_dump(values["run_history"]),
                json_dump(values["feedback"]),
                json_dump(values["changelog"]),
                values["notes"],
                values["created_at"],
                ts,
            ),
        )
        conn.commit()
    print(f"upserted capsule: {args.name} v{values['version']}")


def list_capsules(args: argparse.Namespace) -> None:
    with connect() as conn:
        init_db(conn)
        clauses = []
        params: list[Any] = []
        if args.status:
            clauses.append("status = ?")
            params.append(normalize_status(args.status))
        if args.execution_mode:
            clauses.append("execution_mode = ?")
            params.append(normalize_execution_mode(args.execution_mode))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            SELECT name, display_name, status, execution_mode, version, run_history_json,
                   updated_at, description
            FROM capsules {where}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()
    for row in rows:
        runs = json_load(row["run_history_json"], [])
        success = sum(1 for item in runs if item.get("status") == "success")
        pass_rate = "n/a" if not runs else f"{success / len(runs):.0%}"
        print(
            f"{row['name']}\t{row['display_name'] or row['name']}\t{row['status']}\t"
            f"{row['execution_mode']}\tv{row['version']}\truns={len(runs)}\tpass={pass_rate}\t"
            f"{row['updated_at']}\t{row['description']}"
        )


def capsule_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row["display_name"],
        "status": row["status"],
        "execution_mode": row["execution_mode"],
        "description": row["description"],
        "category": row["category"],
        "tags": json_load(row["tags_json"], []),
        "config": normalize_config(json_load(row["config_json"], {})),
        "method": json_load(row["method_json"], {}),
        "input_schema": json_load(row["input_schema_json"], {}),
        "quality_rules": json_load(row["quality_rules_json"], []),
        "local_assets": normalize_local_assets(json_load(row["local_assets_json"], [])),
        "local_script_path": row["local_script_path"],
        "version": int(row["version"] or 1),
        "run_history": json_load(row["run_history_json"], []),
        "feedback": json_load(row["feedback_json"], []),
        "changelog": json_load(row["changelog_json"], []),
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "contract": build_contract(row),
    }


def show(args: argparse.Namespace) -> None:
    with connect() as conn:
        init_db(conn)
        row = get_capsule(conn, args.name)
        payload = capsule_payload(row)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.contract:
        print(json.dumps(payload["contract"], ensure_ascii=False, indent=2))
        return

    print(f"name: {payload['name']}")
    print(f"display_name: {payload['display_name'] or payload['name']}")
    print(f"status: {payload['status']}")
    print(f"execution_mode: {payload['execution_mode']}")
    print(f"local_script_path: {payload['local_script_path'] or 'n/a'}")
    print(f"version: {payload['version']}")
    print(f"description: {payload['description']}")
    print(f"tags: {', '.join(payload['tags'])}")
    print("\ncontract:")
    print(json.dumps(payload["contract"], ensure_ascii=False, indent=2))
    if payload["feedback"]:
        print("\nfeedback:")
        for item in payload["feedback"][-10:]:
            fix = f" -> {item.get('fix')}" if item.get("fix") else ""
            print(f"- [{item.get('type')}:{item.get('severity')}] {item.get('summary')}{fix}")
    if payload["run_history"]:
        print("\nruns:")
        for item in payload["run_history"][-10:]:
            final = f" final={item.get('final_video')}" if item.get("final_video") else ""
            print(f"- {item.get('at')} {item.get('status')} topic={item.get('topic')}{final}")


def record_run(args: argparse.Namespace) -> None:
    input_params = parse_json(args.input_params_json, "--input-params-json", dict, {})
    compliance_report = parse_json(args.compliance_report_json, "--compliance-report-json", dict, {})
    metrics = parse_json(args.metrics_json, "--metrics-json", dict, {})
    with connect() as conn:
        init_db(conn)
        row = get_capsule(conn, args.name)
        history = json_load(row["run_history_json"], [])
        history.append({
            "at": now(),
            "topic": args.topic,
            "status": args.status,
            "execution_mode": row["execution_mode"],
            "input_params": input_params,
            "workspace_dir": args.workspace_dir,
            "final_video": args.final_video,
            "manifest_path": args.manifest_path,
            "compliance_report": compliance_report,
            "metrics": metrics,
            "notes": args.notes,
            "error": args.error,
        })
        conn.execute(
            "UPDATE capsules SET run_history_json = ?, updated_at = ? WHERE name = ?",
            (json_dump(history[-50:]), now(), args.name),
        )
        conn.commit()
    print(f"recorded run for capsule: {args.name}")


def record_run_dir(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = Path(args.manifest_path).expanduser().resolve() if args.manifest_path else run_dir / "artifact_manifest.json"
    qa_path = Path(args.qa_report).expanduser().resolve() if args.qa_report else run_dir / "reports" / "local_video_qa.json"
    manifest = read_json_file(manifest_path)
    qa_report = read_json_file(qa_path)
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(qa_report, dict):
        qa_report = {}

    final_video = args.final_video or manifest_final_video(manifest)
    if not final_video:
        for sub in ("release", "final"):
            candidates = sorted((run_dir / sub).glob("*.mp4"))
            if candidates:
                final_video = str(candidates[0])
                break
    status = args.status or ("success" if qa_report.get("ok") is True else "needs_review")
    metrics = dict(qa_report.get("probe") or {})
    compliance = qa_report if qa_report else {"ok": None, "note": "QA report not found"}

    args.topic = args.topic
    args.status = status
    args.input_params_json = args.input_params_json
    args.workspace_dir = str(run_dir)
    args.final_video = final_video
    args.manifest_path = str(manifest_path) if manifest_path.exists() else ""
    args.compliance_report_json = json_dump(compliance)
    args.metrics_json = json_dump(metrics)
    args.notes = args.notes
    args.error = args.error
    record_run(args)


def add_feedback(args: argparse.Namespace) -> None:
    with connect() as conn:
        init_db(conn)
        row = get_capsule(conn, args.name)
        feedback = json_load(row["feedback_json"], [])
        feedback.append({
            "at": now(),
            "type": args.feedback_type,
            "severity": args.severity,
            "summary": args.summary,
            "evidence": args.evidence,
            "fix": args.fix,
        })
        conn.execute(
            "UPDATE capsules SET feedback_json = ?, updated_at = ? WHERE name = ?",
            (json_dump(feedback[-100:]), now(), args.name),
        )
        conn.commit()
    print(f"added {args.feedback_type} for capsule: {args.name}")


def is_env_name(value: str) -> bool:
    return bool(ENV_NAME_PATTERN.fullmatch(value))


def contains_secret(value: Any, key_hint: str = "") -> bool:
    if isinstance(value, dict):
        return any(contains_secret(item, str(key)) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_secret(item, key_hint) for item in value)
    if not isinstance(value, str):
        return False
    if is_env_name(value):
        return False
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        return True
    if key_hint and any(pattern.search(key_hint) for pattern in SECRET_KEY_PATTERNS):
        return bool(value.strip())
    return False


def find_remote_values(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(find_remote_values(item, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_remote_values(item, f"{path}[{index}]"))
    elif isinstance(value, str) and REMOTE_VALUE_PATTERN.search(value):
        found.append(f"{path}={value}")
    return found


def doctor(args: argparse.Namespace) -> None:
    issues: list[str] = []
    warnings: list[str] = []
    with connect() as conn:
        init_db(conn)
        row = get_capsule(conn, args.name)
        payload = capsule_payload(row)

    if payload["status"] not in STATUSES:
        issues.append(f"unknown status: {payload['status']}")
    if payload["execution_mode"] not in EXECUTION_MODES:
        issues.append(f"unknown execution_mode: {payload['execution_mode']}")
    if payload["execution_mode"] == "local_script" and not payload["local_script_path"]:
        issues.append("local_script capsule has no local_script_path")
    if payload["execution_mode"] == "preset" and payload["local_script_path"]:
        warnings.append("preset capsule has local_script_path; execution_mode may be wrong")
    if not payload["input_schema"]:
        issues.append("missing input_schema")
    if not payload["quality_rules"]:
        issues.append("missing quality_rules")
    if contains_secret(payload):
        issues.append("possible secret-looking value in capsule data")

    remote_values = find_remote_values(payload)
    if remote_values:
        issues.append("remote/cloud-looking values found; single-user capsules should use local paths only")
        for item in remote_values[:5]:
            issues.append(f"remote value: {item}")

    script_path = payload["local_script_path"]
    if script_path and not Path(script_path).expanduser().exists():
        warnings.append(f"local_script_path does not exist yet: {script_path}")
    for asset in payload["local_assets"]:
        asset_path = asset.get("path") or ""
        if asset_path and Path(asset_path).is_absolute() and not Path(asset_path).expanduser().exists():
            warnings.append(f"local asset path missing: {asset_path}")
    if payload["status"] == "active" and not payload["run_history"]:
        warnings.append("active capsule has no recorded run evidence")
    if payload["status"] == "disabled":
        warnings.append("capsule is disabled")

    if issues or (warnings and not args.warnings_ok):
        print("doctor: issues found")
        for issue in issues:
            print(f"- error: {issue}")
        for warning in warnings:
            print(f"- warning: {warning}")
        sys.exit(1 if issues or not args.warnings_ok else 0)
    if warnings:
        print("doctor: ok with warnings")
        for warning in warnings:
            print(f"- warning: {warning}")
        return
    print("doctor: ok")


CAPSULE_PACKAGE_VERSION = 1
DEFAULT_IMPORT_ASSETS_DIR = Path.home() / ".codex" / "video-production" / "capsule_assets"
UPSTREAM_DEFAULT_CAPSULE_PACKAGES_DIR = Path(__file__).resolve().parents[2] / "capsules"
REPO_DEFAULT_CAPSULE_PACKAGES_DIR = Path(__file__).resolve().parents[1] / "capsules"
DEFAULT_CAPSULE_PACKAGES_DIR = (
    UPSTREAM_DEFAULT_CAPSULE_PACKAGES_DIR
    if UPSTREAM_DEFAULT_CAPSULE_PACKAGES_DIR.exists()
    else REPO_DEFAULT_CAPSULE_PACKAGES_DIR
)
SAFE_ASSET_DIR_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_asset_dir_name(name: str) -> str:
    cleaned = SAFE_ASSET_DIR_PATTERN.sub("_", name).strip("._-")
    return cleaned or "capsule"


def validate_package_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("invalid package path: empty path")
    if "\\" in value:
        raise SystemExit(f"invalid package path: backslash is not allowed: {value}")
    if "//" in value or value.endswith("/"):
        raise SystemExit(f"invalid package path: empty segment is not allowed: {value}")

    package_path = PurePosixPath(value)
    if package_path.is_absolute():
        raise SystemExit(f"invalid package path: absolute path is not allowed: {value}")
    if any(part in ("", ".", "..") for part in package_path.parts):
        raise SystemExit(f"invalid package path: traversal is not allowed: {value}")
    return package_path.as_posix()


def safe_restore_path(base_dir: Path, package_path: str) -> Path:
    base = base_dir.expanduser().resolve()
    dest = (base / package_path).resolve()
    if not dest.is_relative_to(base):
        raise SystemExit(f"invalid package path: restore target escapes assets dir: {package_path}")
    return dest


def export_capsule(args: argparse.Namespace) -> None:
    with connect() as conn:
        init_db(conn)
        row = get_capsule(conn, args.name)
        payload = capsule_payload(row)

    payload.pop("id", None)
    payload.pop("contract", None)

    if contains_secret(payload):
        raise SystemExit("export refused: possible secret-looking value in capsule data (run doctor)")
    remote_values = find_remote_values(payload)
    if remote_values:
        raise SystemExit(
            "export refused: remote/cloud-looking values found:\n"
            + "\n".join(f"- {item}" for item in remote_values[:5])
        )

    files: list[dict] = []
    missing_assets: list[dict] = []
    packaged: list[tuple[Path, str]] = []  # (source file, package_path)
    used_names: set[str] = set()

    def package_name(prefix: str, key: str, source: Path) -> str:
        stem = f"{key}__{source.name}" if key else source.name
        candidate = f"{prefix}/{stem}"
        counter = 1
        while candidate in used_names:
            candidate = f"{prefix}/{counter}__{stem}"
            counter += 1
        used_names.add(candidate)
        return candidate

    for asset in payload["local_assets"]:
        raw_path = asset.get("path") or ""
        if not raw_path:
            continue
        source = Path(raw_path).expanduser()
        if not source.is_file():
            entry = {"asset_key": asset.get("key", ""), "original_path": raw_path}
            if args.allow_missing_assets:
                missing_assets.append(entry)
                continue
            raise SystemExit(
                f"export refused: asset file missing: {raw_path} (use --allow-missing-assets to skip)"
            )
        pkg_path = package_name("assets", asset.get("key", ""), source)
        files.append({
            "package_path": pkg_path,
            "sha256": sha256_file(source),
            "size": source.stat().st_size,
            "original_path": raw_path,
            "asset_key": asset.get("key", ""),
        })
        packaged.append((source, pkg_path))
        asset["path"] = pkg_path

    script_raw = payload.get("local_script_path") or ""
    if script_raw:
        source = Path(script_raw).expanduser()
        if not source.is_file():
            entry = {"asset_key": "local_script", "original_path": script_raw}
            if args.allow_missing_assets:
                missing_assets.append(entry)
            else:
                raise SystemExit(
                    f"export refused: local_script_path missing: {script_raw} (use --allow-missing-assets to skip)"
                )
        else:
            pkg_path = package_name("script", "", source)
            files.append({
                "package_path": pkg_path,
                "sha256": sha256_file(source),
                "size": source.stat().st_size,
                "original_path": script_raw,
                "asset_key": "local_script",
            })
            packaged.append((source, pkg_path))
            payload["local_script_path"] = pkg_path

    manifest = {
        "capsule_package_version": CAPSULE_PACKAGE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "exported_at": now(),
        "capsule": payload,
        "files": files,
        "missing_assets": missing_assets,
    }

    out = Path(args.out).expanduser() if args.out else Path.cwd()
    target = out / f"{args.name}.capsule.zip" if out.is_dir() or not out.suffix else out
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for source, pkg_path in packaged:
            archive.write(source, pkg_path)
    print(f"exported capsule '{args.name}' -> {target}")
    if missing_assets:
        for item in missing_assets:
            print(f"- warning: missing asset skipped: {item['original_path']}")


def import_capsule(args: argparse.Namespace) -> None:
    package = Path(args.package).expanduser()
    if not package.is_file():
        raise SystemExit(f"package not found: {package}")

    with zipfile.ZipFile(package) as archive:
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid capsule package (manifest.json): {exc}") from exc

        pkg_version = manifest.get("capsule_package_version")
        if pkg_version != CAPSULE_PACKAGE_VERSION:
            raise SystemExit(
                f"unsupported capsule_package_version: {pkg_version} (expected {CAPSULE_PACKAGE_VERSION})"
            )
        capsule = manifest.get("capsule")
        if not isinstance(capsule, dict) or not capsule.get("name"):
            raise SystemExit("invalid capsule package: missing capsule payload")

        name = args.name or capsule["name"]

        with connect() as conn:
            init_db(conn)
            existing = conn.execute("SELECT 1 FROM capsules WHERE name = ?", (name,)).fetchone()
            if existing and not args.force:
                raise SystemExit(f"capsule '{name}' already exists (use --force to overwrite)")

        assets_dir = (
            Path(args.assets_dir).expanduser()
            if args.assets_dir
            else DEFAULT_IMPORT_ASSETS_DIR / safe_asset_dir_name(name)
        )
        names_in_zip = set(archive.namelist())
        restored: dict[str, str] = {}
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                raise SystemExit("invalid capsule package: file entry must be an object")
            pkg_path = validate_package_path(entry.get("package_path"))
            if pkg_path not in names_in_zip:
                raise SystemExit(f"package corrupt: missing file {pkg_path}")
            data = archive.read(pkg_path)
            digest = hashlib.sha256(data).hexdigest()
            if digest != entry.get("sha256"):
                raise SystemExit(f"checksum mismatch for {pkg_path}")
            dest = safe_restore_path(assets_dir, pkg_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            restored[pkg_path] = str(dest)

    for asset in capsule.get("local_assets", []):
        if asset.get("path") in restored:
            asset["path"] = restored[asset["path"]]
    if capsule.get("local_script_path") in restored:
        capsule["local_script_path"] = restored[capsule["local_script_path"]]

    changelog = capsule.get("changelog") or []
    changelog.append({
        "version": capsule.get("version", 1),
        "at": now(),
        "source": "import",
        "text": f"imported from {package.name}",
    })
    capsule["changelog"] = changelog

    upsert_args = argparse.Namespace(
        name=name,
        display_name=capsule.get("display_name"),
        status=capsule.get("status"),
        execution_mode=capsule.get("execution_mode"),
        description=capsule.get("description"),
        category=capsule.get("category"),
        tags=",".join(capsule.get("tags", [])) or None,
        config_json=json_dump(capsule.get("config", {})),
        method_json=json_dump(capsule.get("method", {})),
        input_schema_json=json_dump(capsule.get("input_schema", {})),
        quality_rules_json=json_dump(capsule.get("quality_rules", [])),
        local_assets_json=json_dump(capsule.get("local_assets", [])),
        local_script_path=capsule.get("local_script_path", ""),
        notes=capsule.get("notes"),
        bump_version=False,
        changelog="",
        change_source="import",
        replace_existing=bool(args.force),
    )
    upsert(upsert_args)

    with connect() as conn:
        init_db(conn)
        conn.execute(
            """
            UPDATE capsules SET version = ?, run_history_json = ?, feedback_json = ?, changelog_json = ?,
                   updated_at = ? WHERE name = ?
            """,
            (
                int(capsule.get("version", 1)),
                json_dump(capsule.get("run_history", [])),
                json_dump(capsule.get("feedback", [])),
                json_dump(capsule.get("changelog", [])),
                now(),
                name,
            ),
        )
        conn.commit()

    print(f"imported capsule '{name}' (assets in {assets_dir})")
    for item in manifest.get("missing_assets", []):
        print(f"- warning: package was exported without asset: {item.get('original_path')}")

    doctor_args = argparse.Namespace(name=name, warnings_ok=True)
    doctor(doctor_args)


def install_defaults(args: argparse.Namespace) -> None:
    packages_dir = Path(args.dir).expanduser() if args.dir else DEFAULT_CAPSULE_PACKAGES_DIR
    packages = sorted(packages_dir.glob("*.capsule.zip"))
    if not packages:
        raise SystemExit(f"no .capsule.zip packages found in {packages_dir}")

    with connect() as conn:
        init_db(conn)
        existing_names = {row["name"] for row in conn.execute("SELECT name FROM capsules").fetchall()}

    installed = skipped = 0
    for package in packages:
        name = package.name.removesuffix(".capsule.zip")
        if name in existing_names and not args.force:
            print(f"skip (exists): {name}")
            skipped += 1
            continue
        import_args = argparse.Namespace(
            package=str(package), assets_dir="", name="", force=args.force or name in existing_names,
        )
        import_capsule(import_args)
        installed += 1
    print(f"install-defaults done: {installed} installed, {skipped} skipped ({packages_dir})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="initialize or migrate the local capsule DB")

    def run_init(_args: argparse.Namespace) -> None:
        with connect() as conn:
            init_db(conn)
        print(f"initialized {db_path()}")

    init.set_defaults(func=run_init)

    up = sub.add_parser("upsert", help="create or update a local capsule")
    up.add_argument("--name", required=True)
    up.add_argument("--display-name")
    up.add_argument("--status")
    up.add_argument("--execution-mode", choices=sorted(EXECUTION_MODES | {"script_package"}))
    up.add_argument("--description")
    up.add_argument("--category")
    up.add_argument("--tags")
    up.add_argument("--config-json")
    up.add_argument("--method-json")
    up.add_argument("--input-schema-json")
    up.add_argument("--quality-rules-json")
    up.add_argument("--local-assets-json")
    up.add_argument("--local-script-path")
    up.add_argument("--notes")
    up.add_argument("--bump-version", action="store_true")
    up.add_argument("--changelog", default="")
    up.add_argument("--change-source", default="manual")
    up.set_defaults(func=upsert)

    ls = sub.add_parser("list", help="list capsules")
    ls.add_argument("--status")
    ls.add_argument("--execution-mode", choices=sorted(EXECUTION_MODES | {"script_package"}))
    ls.set_defaults(func=list_capsules)

    sh = sub.add_parser("show", help="show one capsule")
    sh.add_argument("name")
    sh.add_argument("--json", action="store_true")
    sh.add_argument("--contract", action="store_true")
    sh.set_defaults(func=show)

    rr = sub.add_parser("record-run", help="append run evidence")
    rr.add_argument("--name", required=True)
    rr.add_argument("--topic", default="")
    rr.add_argument("--status", required=True)
    rr.add_argument("--input-params-json")
    rr.add_argument("--workspace-dir", default="")
    rr.add_argument("--final-video", default="")
    rr.add_argument("--manifest-path", default="")
    rr.add_argument("--compliance-report-json")
    rr.add_argument("--metrics-json")
    rr.add_argument("--notes", default="")
    rr.add_argument("--error", default="")
    rr.set_defaults(func=record_run)

    rrd = sub.add_parser("record-run-dir", help="append run evidence from a local run directory")
    rrd.add_argument("--name", required=True)
    rrd.add_argument("--run-dir", required=True)
    rrd.add_argument("--topic", default="")
    rrd.add_argument("--status", default="")
    rrd.add_argument("--input-params-json")
    rrd.add_argument("--manifest-path", default="")
    rrd.add_argument("--qa-report", default="")
    rrd.add_argument("--final-video", default="")
    rrd.add_argument("--notes", default="")
    rrd.add_argument("--error", default="")
    rrd.set_defaults(func=record_run_dir)

    fb = sub.add_parser("add-feedback", help="append pitfall, review, or user feedback")
    fb.add_argument("--name", required=True)
    fb.add_argument("--type", dest="feedback_type", default="pitfall")
    fb.add_argument("--severity", default="warning")
    fb.add_argument("--summary", required=True)
    fb.add_argument("--evidence", default="")
    fb.add_argument("--fix", default="")
    fb.set_defaults(func=add_feedback)

    pf = sub.add_parser("add-pitfall", help="compatibility alias for add-feedback --type pitfall")
    pf.add_argument("--name", required=True)
    pf.add_argument("--what", required=True)
    pf.add_argument("--where", dest="evidence", default="")
    pf.add_argument("--fix", default="")
    pf.add_argument("--severity", default="warning")

    def run_pitfall(args: argparse.Namespace) -> None:
        args.feedback_type = "pitfall"
        args.summary = args.what
        add_feedback(args)

    pf.set_defaults(func=run_pitfall)

    doc = sub.add_parser("doctor", help="check one local capsule")
    doc.add_argument("name")
    doc.add_argument("--warnings-ok", action="store_true")
    doc.set_defaults(func=doctor)

    ex = sub.add_parser("export", help="export a capsule to a shareable .capsule.zip")
    ex.add_argument("name")
    ex.add_argument("--out", default="", help="output directory or file path (default: cwd)")
    ex.add_argument("--allow-missing-assets", action="store_true")
    ex.set_defaults(func=export_capsule)

    im = sub.add_parser("import", help="import a .capsule.zip into the local store")
    im.add_argument("package")
    im.add_argument("--assets-dir", default="", help=f"asset landing dir (default: {DEFAULT_IMPORT_ASSETS_DIR}/<name>)")
    im.add_argument("--name", default="", help="import under a different capsule name")
    im.add_argument("--force", action="store_true", help="overwrite an existing capsule with the same name")
    im.set_defaults(func=import_capsule)

    inst = sub.add_parser("install-defaults", help="import all bundled .capsule.zip packages from the repo capsules/ dir")
    inst.add_argument("--dir", default="", help=f"packages dir (default: {DEFAULT_CAPSULE_PACKAGES_DIR})")
    inst.add_argument("--force", action="store_true", help="overwrite capsules that already exist")
    inst.set_defaults(func=install_defaults)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
