#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FILES = [
    "capsule.yaml",
    "CARD.md",
    "contracts/runtime.yaml",
    "contracts/input_schema.yaml",
    "quality/rules.yaml",
    "assets/index.yaml",
    "learning/promoted_lessons.yaml",
]
ALLOWED_ASSET_ROLES = {
    "bgm",
    "sfx",
    "font",
    "intro_template",
    "style_reference",
    "character_reference",
    "source_media",
    "template",
}
ALLOWED_REUSE = {"always", "reference_only"}
CANONICAL_READ_ORDER_STAGES = ("routing", "planning", "generation", "qa", "learning")
SCANNABLE_SUFFIXES = {".md", ".yaml", ".yml", ".json"}
SECRET_OR_REMOTE = re.compile(
    r"(https?://|s3://|oss://|qiniu://|bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
OUTPUT_PATH = re.compile(r"(^|[\\/])output([\\/]|$)", re.IGNORECASE)
LOCAL_PATH = re.compile(
    r"(?i)(/Users/[^\s'\"()]+|/home/[^\s'\"()]+|/tmp/[^\s'\"()]+|\.codex(?:/[^\s'\"()]+)?|capsules\.sqlite)"
)
EVIDENCE_TOKENS = re.compile(r"(?i)\b(feedback_json|run_history)\b")
RECIPE_FEEDBACK = re.compile(r"(?i)\bfeedback\b")
ARTIFACT_MANIFEST = re.compile(r"(?i)\bartifact_manifest\.json\b")


def _read_yaml(path: Path, errors: list[str], fallback: Any) -> Any:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return fallback
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or fallback
    except yaml.YAMLError as exc:
        errors.append(f"invalid YAML {path}: {exc}")
        return fallback


def _iter_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            values.extend(_iter_strings(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_iter_strings(item))
    return values


def _check_string_content(
    label: str,
    value: str,
    errors: list[str],
    *,
    check_evidence: bool = True,
    allow_artifact_manifest: bool = False,
) -> None:
    if SECRET_OR_REMOTE.search(value):
        errors.append(f"secret or remote-looking value in {label}")
    has_output_path = bool(OUTPUT_PATH.search(value))
    if has_output_path:
        errors.append(f"output path found in recipe/package file: {label}")
    if LOCAL_PATH.search(value) and not has_output_path:
        errors.append(f"local path found in recipe/package file: {label}")
    if check_evidence and EVIDENCE_TOKENS.search(value):
        errors.append(f"legacy evidence token found in recipe/package file: {label}")
    if check_evidence and not allow_artifact_manifest and ARTIFACT_MANIFEST.search(value):
        errors.append(f"runtime manifest token found in recipe/package file: {label}")
    if check_evidence and label.endswith(".md") and RECIPE_FEEDBACK.search(value):
        errors.append(f"feedback-shaped text found in recipe/package file: {label}")


def _check_text_file(
    path: Path,
    errors: list[str],
    *,
    check_evidence: bool = True,
    allow_artifact_manifest: bool = False,
) -> None:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return
    _check_string_content(
        str(path),
        path.read_text(encoding="utf-8"),
        errors,
        check_evidence=check_evidence,
        allow_artifact_manifest=allow_artifact_manifest,
    )


def _check_structured_file(
    path: Path,
    errors: list[str],
    *,
    check_evidence: bool = True,
    allow_artifact_manifest: bool = False,
) -> None:
    if path.suffix.lower() == ".md":
        _check_text_file(
            path,
            errors,
            check_evidence=check_evidence,
            allow_artifact_manifest=allow_artifact_manifest,
        )
        return

    if not path.exists():
        errors.append(f"missing file: {path}")
        return

    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() == ".json":
            payload = json.loads(text) if text.strip() else None
        else:
            payload = yaml.safe_load(text) if text.strip() else None
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        errors.append(f"invalid structured file {path}: {exc}")
        return

    for value in _iter_strings(payload):
        _check_string_content(
            str(path),
            value,
            errors,
            check_evidence=check_evidence,
            allow_artifact_manifest=allow_artifact_manifest,
        )


def _is_package_relative_path(root: Path, rel_path: str) -> bool:
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return False
    return (root / candidate).resolve().is_relative_to(root)


def _asset_file_path(root: Path, rel_path: str) -> Path:
    return (root / "assets" / rel_path).resolve()


def _is_asset_relative_path(root: Path, rel_path: str) -> bool:
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return False
    return _asset_file_path(root, rel_path).is_relative_to((root / "assets").resolve())


def _scan_package_surfaces(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "scripts" in path.relative_to(root).parts:
            continue
        suffix = path.suffix.lower()
        if suffix not in SCANNABLE_SUFFIXES and path.name not in {"CARD.md", "capsule.yaml"}:
            continue
        _check_structured_file(
            path,
            errors,
            check_evidence=path != root / "quality" / "rules.yaml",
            allow_artifact_manifest=path == root / "quality" / "rules.yaml",
        )


def validate_capsule_dir(capsule_dir: str | Path, warnings_ok: bool = False) -> dict[str, Any]:
    root = Path(capsule_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        return {"ok": False, "errors": [f"not a directory: {root}"], "warnings": []}

    for rel_path in REQUIRED_FILES:
        if not (root / rel_path).exists():
            errors.append(f"missing required file: {rel_path}")

    capsule = _read_yaml(root / "capsule.yaml", errors, {})
    runtime = _read_yaml(root / "contracts" / "runtime.yaml", errors, {})
    rules_doc = _read_yaml(root / "quality" / "rules.yaml", errors, {})
    assets_doc = _read_yaml(root / "assets" / "index.yaml", errors, {})

    if not isinstance(capsule, dict):
        errors.append("capsule.yaml must be an object")
        capsule = {}
    if not isinstance(runtime, dict):
        errors.append("contracts/runtime.yaml must be an object")
        runtime = {}
    if not isinstance(rules_doc, dict):
        errors.append("quality/rules.yaml must be an object")
        rules_doc = {}
    if not isinstance(assets_doc, dict):
        errors.append("assets/index.yaml must be an object")
        assets_doc = {}

    for key in ("schema_version", "name", "version", "status", "execution_mode", "read_order", "entrypoints"):
        if key not in capsule:
            errors.append(f"capsule.yaml missing key: {key}")
    if capsule.get("schema_version") != "capsule.package.v1":
        errors.append("capsule.yaml schema_version must be capsule.package.v1")
    for key in ("source", "legacy_version", "converted_at"):
        if key in capsule:
            errors.append(f"migration metadata is not allowed in active package: capsule.yaml {key}")

    read_order = capsule.get("read_order")
    declared_read_order_paths: set[str] = set()
    if isinstance(read_order, dict):
        actual_stages = set(read_order)
        expected_stages = set(CANONICAL_READ_ORDER_STAGES)
        if actual_stages != expected_stages:
            missing = sorted(expected_stages - actual_stages)
            extra = sorted(actual_stages - expected_stages)
            details = []
            if missing:
                details.append(f"missing stages: {', '.join(missing)}")
            if extra:
                details.append(f"unexpected stages: {', '.join(extra)}")
            errors.append(f"read_order must define canonical stages ({', '.join(CANONICAL_READ_ORDER_STAGES)}); {'; '.join(details)}")
        for stage in CANONICAL_READ_ORDER_STAGES:
            paths = read_order.get(stage)
            if not isinstance(paths, list):
                errors.append(f"read_order.{stage} must be a list")
                continue
            for rel_path in paths:
                declared_read_order_paths.add(str(rel_path))
                target = (root / str(rel_path)).resolve()
                if not target.is_relative_to(root):
                    errors.append(f"read_order path escapes capsule: {rel_path}")
                    continue
                if not target.exists():
                    errors.append(f"read_order file missing: {stage}: {rel_path}")
                    continue
    else:
        errors.append("capsule.yaml read_order must be an object")

    recipes_dir = root / "recipes"
    if recipes_dir.is_dir():
        for recipe in sorted(recipes_dir.glob("*.md")):
            rel_path = recipe.relative_to(root).as_posix()
            if rel_path not in declared_read_order_paths:
                errors.append(f"unreferenced recipe file: {rel_path}")

    if capsule.get("execution_mode") == "local_script":
        entrypoints = capsule.get("entrypoints") if isinstance(capsule.get("entrypoints"), dict) else {}
        local_script = entrypoints.get("local_script")
        if not local_script:
            errors.append("local_script capsule missing entrypoints.local_script")
        else:
            target = (root / str(local_script)).resolve()
            if not target.is_relative_to(root):
                errors.append(f"local_script entrypoint escapes capsule: {local_script}")
            elif not target.is_file():
                errors.append(f"local_script entrypoint missing: {local_script}")

    if not isinstance(runtime.get("roles"), dict):
        errors.append("contracts/runtime.yaml roles must be an object")
    if not isinstance(runtime.get("output_contract"), dict):
        errors.append("contracts/runtime.yaml output_contract must be an object")

    rules = rules_doc.get("rules")
    if not isinstance(rules, list):
        errors.append("quality/rules.yaml must contain rules list")
    else:
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"quality rule {index} must be an object")
            elif not rule.get("id"):
                errors.append(f"quality rule {index} missing id")

    assets = assets_doc.get("assets")
    if not isinstance(assets, list):
        errors.append("assets/index.yaml must contain assets list")
    else:
        for asset in assets:
            if not isinstance(asset, dict):
                errors.append("asset entry must be an object")
                continue
            key = str(asset.get("key") or asset.get("path") or "<unknown>")
            role = str(asset.get("role") or "")
            reuse = str(asset.get("reuse") or "")
            path = str(asset.get("path") or "")
            if role and role not in ALLOWED_ASSET_ROLES:
                errors.append(f"asset has unsupported role: {key}: {role}")
            if reuse and reuse not in ALLOWED_REUSE:
                errors.append(f"asset has unsupported reuse: {key}: {reuse}")
            if path:
                _check_string_content(f"asset path {key}", path, errors)
                if not _is_asset_relative_path(root, path):
                    errors.append(f"asset path escapes capsule: {key}: {path}")
                elif not _asset_file_path(root, path).is_file():
                    errors.append(f"asset file missing: {key}: {path}")
            for text in _iter_strings(asset):
                _check_string_content(f"asset {key}", text, errors)

    _scan_package_surfaces(root, errors)

    ok = not errors and (warnings_ok or not warnings)
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "capsule_dir": str(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a capsule package directory.")
    parser.add_argument("capsule_dir")
    parser.add_argument("--warnings-ok", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_capsule_dir(args.capsule_dir, warnings_ok=args.warnings_ok)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("capsule package validation:", "ok" if report["ok"] else "failed")
        for error in report["errors"]:
            print(f"- error: {error}")
        for warning in report["warnings"]:
            print(f"- warning: {warning}")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
