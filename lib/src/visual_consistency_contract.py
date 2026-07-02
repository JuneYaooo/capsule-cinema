"""Provider-agnostic visual style and character consistency contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STYLE_REPORT_SCHEMA = "capsule_cinema.style_consistency_report.v1"
STRICT_REFERENCE_LOCK = "strict_reference_lock"
TEXT_ONLY_SOFT_LOCK = "text_only_soft_lock"
INCONSISTENT_OR_UNKNOWN = "inconsistent_or_unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value)
            if value[key] not in (None, "", [], {})
        }
    if isinstance(value, (list, tuple, set)):
        return [_canonical(item) for item in value if item not in (None, "", [], {})]
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _block(title: str, lines: list[str]) -> str:
    content = [line for line in lines if line]
    return f"[{title}]\n" + "\n".join(content)


def _style_lines(style_contract: dict[str, Any]) -> list[str]:
    return [
        f"name: {style_contract.get('style_name') or style_contract.get('name') or 'locked_style'}",
        f"description: {style_contract.get('style_description') or style_contract.get('description') or ''}",
        "fixed traits: " + "; ".join(_clean_list(style_contract.get("fixed_style_traits") or style_contract.get("fixed_traits"))),
        "allowed variations: " + "; ".join(
            _clean_list(style_contract.get("allowed_style_variations") or style_contract.get("allowed_variations"))
        ),
    ]


def _character_lines(character_bible: dict[str, Any]) -> list[str]:
    return [
        f"id: {character_bible.get('character_id') or character_bible.get('id') or 'main_character'}",
        f"identity anchor: {character_bible.get('identity_anchor') or character_bible.get('description') or ''}",
        "fixed traits: " + "; ".join(_clean_list(character_bible.get("fixed_traits"))),
        "allowed variations: " + "; ".join(_clean_list(character_bible.get("allowed_variations"))),
        "forbidden drift: " + "; ".join(
            _clean_list(character_bible.get("forbidden_drift") or character_bible.get("negative_traits"))
        ),
    ]


def _negative_lines(negative_style_rules: Any) -> list[str]:
    rules = _clean_list(negative_style_rules) or [
        "do not change the character identity",
        "do not switch art style, rendering medium, linework, color system, or age impression mid-batch",
        "do not copy a reference pose when only identity/style should be inherited",
    ]
    return rules


def prompt_style_hash(
    *,
    style_contract: dict[str, Any],
    character_bible: dict[str, Any],
    aspect_ratio: str,
    negative_style_rules: Any = None,
) -> str:
    """Hash only stable style/identity constraints, never scene action."""
    payload = {
        "aspect_ratio": str(aspect_ratio or ""),
        "style_contract": _canonical(style_contract),
        "character_bible": _canonical(character_bible),
        "negative_style_rules": _canonical(_negative_lines(negative_style_rules)),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:16]


def compile_scene_prompt(
    scene: dict[str, Any],
    style_contract: dict[str, Any] | None,
    character_bible: dict[str, Any] | None,
    aspect_ratio: str,
    negative_style_rules: Any = None,
    reference_image_paths: list[str] | None = None,
    strict_reference_required: bool = True,
) -> dict[str, Any]:
    """Compile a scene prompt from stable contract blocks plus scene action."""
    style = _as_mapping(style_contract)
    character = _as_mapping(character_bible)
    refs = _clean_list(reference_image_paths)
    style_hash = prompt_style_hash(
        style_contract=style,
        character_bible=character,
        aspect_ratio=aspect_ratio,
        negative_style_rules=negative_style_rules,
    )
    action = (
        scene.get("action")
        or scene.get("description")
        or scene.get("image_prompt")
        or scene.get("image_prompt_chinese")
        or scene.get("image_prompt_english")
        or ""
    )
    sections = [
        _block("ASPECT", [str(aspect_ratio or "")]),
        _block("STYLE CONTRACT", _style_lines(style)),
        _block("CHARACTER BIBLE", _character_lines(character)),
        _block("SCENE ACTION", [str(action)]),
        _block("CONTINUITY ANCHOR", [str(scene.get("continuity_anchor") or scene.get("continuity_notes") or "")]),
        _block("ACTOR STATE", [str(scene.get("actor_state") or "")]),
        _block("NEGATIVE STYLE/IDENTITY DRIFT", _negative_lines(negative_style_rules)),
    ]
    if refs or strict_reference_required:
        mode = STRICT_REFERENCE_LOCK
    elif style or character:
        mode = TEXT_ONLY_SOFT_LOCK
    else:
        mode = INCONSISTENT_OR_UNKNOWN
    return {
        "scene_id": scene.get("scene_id") or scene.get("index") or "",
        "compiled_prompt": "\n\n".join(sections).strip(),
        "prompt_style_hash": style_hash,
        "consistency_mode": mode,
        "reference_image_paths": refs,
        "style_contract": _canonical(style),
        "character_bible": _canonical(character),
    }


def _record_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    merged = dict(payload)
    merged.update({key: value for key, value in entry.items() if key != "payload"})
    return merged


def _image_records(prompt_index: dict[str, Any]) -> list[dict[str, Any]]:
    entries = prompt_index.get("entries") if isinstance(prompt_index.get("entries"), list) else []
    records: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        record = _record_payload(raw)
        category = str(record.get("category") or "").strip().lower()
        has_prompt_contract = any(
            key in record
            for key in (
                "final_prompt_used",
                "final_prompt",
                "prompt_style_hash",
                "consistency_mode",
                "reference_image_paths",
            )
        )
        if category == "image" or (not category and has_prompt_contract):
            records.append(record)
    return records


def _final_prompt(record: dict[str, Any]) -> str:
    for key in ("final_prompt_used", "final_prompt", "actual_prompt", "compiled_prompt", "image_prompt"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _reference_paths(record: dict[str, Any]) -> list[str]:
    value = record.get("reference_image_paths")
    if value is None:
        value = record.get("reference_images") or record.get("reference_image_path")
    return _clean_list(value)


def _attempts(record: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = record.get("attempts")
    if isinstance(attempts, list):
        return [item for item in attempts if isinstance(item, dict)]
    return []


def _add_check(
    checks: list[dict[str, Any]],
    blockers: set[str],
    warnings: set[str],
    ok: bool,
    check_id: str,
    message: str,
    severity: str = "blocker",
    **extra: Any,
) -> None:
    checks.append({"id": check_id, "ok": ok, "severity": severity, "message": message, **extra})
    if ok:
        return
    if severity == "blocker":
        blockers.add(check_id)
    else:
        warnings.add(check_id)


def validate_prompt_index(
    prompt_index: dict[str, Any],
    *,
    strict_character_required: bool = False,
    soft_consistency_ack: bool = False,
) -> dict[str, Any]:
    """Validate actual image prompts and reference downgrade state."""
    records = _image_records(prompt_index)
    checks: list[dict[str, Any]] = []
    blockers: set[str] = set()
    warnings: set[str] = set()

    _add_check(
        checks,
        blockers,
        warnings,
        bool(records),
        "image_prompt_records_present",
        "prompt index contains image prompt records",
    )

    style_hashes: set[str] = set()
    missing_final_prompt_scene_ids: list[Any] = []
    missing_hash_scene_ids: list[Any] = []
    downgraded_scene_ids: list[Any] = []
    missing_reference_scene_ids: list[Any] = []
    fallback_reason_missing_scene_ids: list[Any] = []

    for index, record in enumerate(records, start=1):
        scene_id = record.get("scene_id") or record.get("index") or index
        final_prompt = _final_prompt(record)
        style_hash = str(record.get("prompt_style_hash") or "").strip()
        mode = str(record.get("consistency_mode") or INCONSISTENT_OR_UNKNOWN).strip()
        refs = _reference_paths(record)
        attempts = _attempts(record)

        if not final_prompt:
            missing_final_prompt_scene_ids.append(scene_id)
        if not style_hash:
            missing_hash_scene_ids.append(scene_id)
        else:
            style_hashes.add(style_hash)

        if strict_character_required:
            if mode == TEXT_ONLY_SOFT_LOCK and not soft_consistency_ack:
                downgraded_scene_ids.append(scene_id)
            elif mode != STRICT_REFERENCE_LOCK and not soft_consistency_ack:
                downgraded_scene_ids.append(scene_id)
            if not refs and not soft_consistency_ack:
                missing_reference_scene_ids.append(scene_id)

        fallback_happened = len(attempts) > 1 or any(str(item.get("status") or "").lower() not in {"", "success", "pass"} for item in attempts)
        if fallback_happened:
            has_reason = bool(record.get("fallback_reason")) or any(item.get("fallback_reason") for item in attempts)
            if not has_reason:
                fallback_reason_missing_scene_ids.append(scene_id)

    _add_check(
        checks,
        blockers,
        warnings,
        not missing_final_prompt_scene_ids,
        "final_prompt_used_missing",
        "each generated image record must include the actual final prompt used",
        missing_scene_ids=missing_final_prompt_scene_ids,
    )
    _add_check(
        checks,
        blockers,
        warnings,
        not missing_hash_scene_ids,
        "prompt_style_hash_missing",
        "each generated image record must include prompt_style_hash",
        missing_scene_ids=missing_hash_scene_ids,
    )
    _add_check(
        checks,
        blockers,
        warnings,
        len(style_hashes) <= 1,
        "prompt_style_hash_drift",
        "all final image prompts must share one stable style hash",
        style_hashes=sorted(style_hashes),
    )
    _add_check(
        checks,
        blockers,
        warnings,
        not downgraded_scene_ids,
        "strict_reference_downgraded_without_ack",
        "strict character consistency cannot silently downgrade to text-only soft lock",
        missing_scene_ids=downgraded_scene_ids,
    )
    _add_check(
        checks,
        blockers,
        warnings,
        not missing_reference_scene_ids,
        "strict_reference_paths_missing",
        "strict character consistency requires reference image paths",
        missing_scene_ids=missing_reference_scene_ids,
    )
    _add_check(
        checks,
        blockers,
        warnings,
        not fallback_reason_missing_scene_ids,
        "fallback_reason_missing",
        "fallback attempts must record fallback_reason",
        missing_scene_ids=fallback_reason_missing_scene_ids,
    )

    return {
        "schema": STYLE_REPORT_SCHEMA,
        "created_at": _now(),
        "ok": not blockers,
        "strict_character_required": bool(strict_character_required),
        "soft_consistency_ack": bool(soft_consistency_ack),
        "summary": {
            "image_prompt_records": len(records),
            "prompt_style_hashes": sorted(style_hashes),
            "consistency_modes": sorted(
                {
                    str(record.get("consistency_mode") or INCONSISTENT_OR_UNKNOWN)
                    for record in records
                }
            ),
        },
        "checks": checks,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
    }


def read_json(path: str | Path, fallback: Any = None) -> Any:
    target = Path(path).expanduser()
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def style_consistency_issue(report: dict[str, Any], path: str | Path = "") -> dict[str, Any] | None:
    if not isinstance(report, dict) or not report:
        return None
    if report.get("ok") is not False:
        return None
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    return {
        "id": "style_consistency_failed",
        "severity": "blocker",
        "detail": ", ".join(str(item) for item in blockers) or "style consistency report failed",
        "path": str(path or ""),
        "report": report,
    }
