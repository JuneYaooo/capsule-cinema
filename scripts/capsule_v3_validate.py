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
SECRET_OR_REMOTE = re.compile(
    r"(https?://|s3://|oss://|qiniu://|bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
OUTPUT_PATH = re.compile(r"(^|[\\/])output([\\/]|$)", re.IGNORECASE)


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


def _check_string_content(label: str, value: str, errors: list[str]) -> None:
    if SECRET_OR_REMOTE.search(value):
        errors.append(f"secret or remote-looking value in {label}")
    if OUTPUT_PATH.search(value):
        errors.append(f"output path found in recipe/package file: {label}")


def _check_text_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return
    _check_string_content(str(path), path.read_text(encoding="utf-8"), errors)


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
    if capsule.get("schema_version") != "capsule.v3":
        errors.append("capsule.yaml schema_version must be capsule.v3")

    read_order = capsule.get("read_order")
    if isinstance(read_order, dict):
        for stage, paths in read_order.items():
            if not isinstance(paths, list):
                errors.append(f"read_order.{stage} must be a list")
                continue
            for rel_path in paths:
                target = (root / str(rel_path)).resolve()
                if not target.is_relative_to(root):
                    errors.append(f"read_order path escapes capsule: {rel_path}")
                    continue
                if not target.exists():
                    errors.append(f"read_order file missing: {stage}: {rel_path}")
                    continue
                if target.is_file():
                    _check_text_file(target, errors)
    else:
        errors.append("capsule.yaml read_order must be an object")

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
            for text in _iter_strings(asset):
                _check_string_content(f"asset {key}", text, errors)

    _check_text_file(root / "CARD.md", errors)
    for text in _iter_strings(capsule):
        _check_string_content("capsule.yaml", text, errors)
    for text in _iter_strings(runtime):
        _check_string_content("contracts/runtime.yaml", text, errors)
    for text in _iter_strings(rules_doc):
        _check_string_content("quality/rules.yaml", text, errors)
    for text in _iter_strings(assets_doc):
        _check_string_content("assets/index.yaml", text, errors)

    ok = not errors and (warnings_ok or not warnings)
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "capsule_dir": str(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Capsule v3 package directory.")
    parser.add_argument("capsule_dir")
    parser.add_argument("--warnings-ok", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_capsule_dir(args.capsule_dir, warnings_ok=args.warnings_ok)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("capsule v3 validation:", "ok" if report["ok"] else "failed")
        for error in report["errors"]:
            print(f"- error: {error}")
        for warning in report["warnings"]:
            print(f"- warning: {warning}")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
