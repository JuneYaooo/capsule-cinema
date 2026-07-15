#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from src.capsule_gate_runner import available_checker_names  # noqa: E402
from src.capsule_content_scope import (  # noqa: E402
    audit_reusable_surfaces,
    validate_content_scope_contract,
)


REQUIRED_FILES = [
    "index.md",
    "capsule.yaml",
    "CARD.md",
    "contracts/runtime.yaml",
    "contracts/input_schema.yaml",
    "contracts/content_scope.yaml",
    "quality/release_gates.yaml",
    "quality/rules.yaml",
    "assets/index.yaml",
    "learning/promoted_lessons.yaml",
    "examples/illustrative.yaml",
]
VIDEO_OKF_PROFILE = "video.okf.capsule.v1"
RECIPE_STAGE_BY_DOMAIN = {
    "audio": "planning",
    "copy": "planning",
    "motion": "generation",
    "structure": "planning",
    "visual": "planning",
}
ALLOWED_ASSET_ROLES = {
    "bgm",
    "sfx",
    "font",
    "intro_template",
    "style_reference",
    "character_reference",
    "voice_reference",
    "pose_reference",
    "performance_reference",
    "source_video_reference",
    "source_video",
    "source_audio",
    "source_image",
    "source_media",
    "template",
    "overlay",
}
ALLOWED_REUSE = {"always", "reference_only"}
ALLOWED_EVIDENCE_LEVELS = {
    "unspecified",
    "L0_metadata_only",
    "L1_metadata_plus_keyframes",
    "L2_multimodal_probe",
    "L3_production_capsule",
}
PRODUCTION_CONTRACT_SCHEMA = "capsule.production_contract.v1"
ALLOWED_OUTPUT_REQUIREMENTS = {"required", "optional", "none", "external"}
ALLOWED_GATE_PHASES = {"preflight", "pre_render", "post_render", "qa", "release"}
ALLOWED_GATE_SEVERITIES = {"blocker", "warning", "manual_blocker"}
ALLOWED_VIDEO_ELEMENT_SECTIONS = {"fixed", "defaults", "user_overridable", "forbidden"}
CANONICAL_READ_ORDER_STAGES = ("routing", "planning", "generation", "qa", "learning")
SAFE_METADATA_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SCANNABLE_SUFFIXES = {".md", ".yaml", ".yml", ".json"}
SCRIPT_TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".txt"}
SECRET_OR_REMOTE = re.compile(
    r"(https?://|s3://|oss://|qiniu://|bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
SCRIPT_SECRET = re.compile(
    r"(bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
OUTPUT_PATH = re.compile(r"(^|[\\/])output([\\/]|$)", re.IGNORECASE)
LOCAL_PATH = re.compile(
    r"(?i)(/Users/[^\s'\"()]+|/home/[^\s'\"()]+|/tmp/[^\s'\"()]+|\.codex(?:/[^\s'\"()]+)?)"
)
EVIDENCE_TOKENS = re.compile(r"(?i)\b(feedback_json|run_history)\b")
RECIPE_FEEDBACK = re.compile(r"(?i)\bfeedback\b")
ARTIFACT_MANIFEST = re.compile(r"(?i)\bartifact_manifest\.json\b")
MIGRATION_PLACEHOLDER = re.compile(r"No capsule-specific rules were migrated", re.IGNORECASE)


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


def _parse_markdown_frontmatter(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append(f"missing YAML frontmatter: {path}")
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            raw = "\n".join(lines[1:index])
            try:
                data = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                errors.append(f"invalid YAML frontmatter {path}: {exc}")
                return None
            if not isinstance(data, dict):
                errors.append(f"YAML frontmatter must be an object: {path}")
                return None
            return data
    errors.append(f"unterminated YAML frontmatter: {path}")
    return None


def _require_frontmatter_keys(label: str, meta: dict[str, Any] | None, keys: tuple[str, ...], errors: list[str]) -> None:
    if meta is None:
        return
    for key in keys:
        value = meta.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{label} frontmatter missing key: {key}")


def _validate_markdown_concepts(root: Path, errors: list[str]) -> None:
    index_meta = _parse_markdown_frontmatter(root / "index.md", errors)
    _require_frontmatter_keys(
        "index.md",
        index_meta,
        ("okf_version", "type", "title", "description", "profile"),
        errors,
    )
    if index_meta is not None:
        if index_meta.get("profile") != VIDEO_OKF_PROFILE:
            errors.append(f"index.md frontmatter profile must be {VIDEO_OKF_PROFILE}")
        if index_meta.get("type") != "Video Capsule Bundle Index":
            errors.append("index.md frontmatter type must be Video Capsule Bundle Index")

    card_meta = _parse_markdown_frontmatter(root / "CARD.md", errors)
    _require_frontmatter_keys("CARD.md", card_meta, ("type", "title", "description"), errors)
    if card_meta is not None and card_meta.get("type") != "Video Capsule Card":
        errors.append("CARD.md frontmatter type must be Video Capsule Card")

    recipes_dir = root / "recipes"
    if not recipes_dir.is_dir():
        errors.append("missing directory: recipes")
        return
    for recipe in sorted(recipes_dir.glob("*.md")):
        rel_path = recipe.relative_to(root).as_posix()
        domain = recipe.stem
        meta = _parse_markdown_frontmatter(recipe, errors)
        _require_frontmatter_keys(
            rel_path,
            meta,
            ("type", "title", "description", "stage", "domain"),
            errors,
        )
        if meta is None:
            continue
        if meta.get("type") != "Video Recipe":
            errors.append(f"{rel_path} frontmatter type must be Video Recipe")
        if meta.get("domain") != domain:
            errors.append(f"{rel_path} frontmatter domain must match filename: {domain}")
        expected_stage = RECIPE_STAGE_BY_DOMAIN.get(domain)
        if expected_stage is not None and meta.get("stage") != expected_stage:
            errors.append(f"{rel_path} frontmatter stage must be {expected_stage}")


def _validate_production_contract(root: Path, errors: list[str]) -> None:
    path = root / "contracts" / "production_contract.yaml"
    if not path.exists():
        return
    contract = _read_yaml(path, errors, {})
    if not isinstance(contract, dict):
        errors.append("contracts/production_contract.yaml must be an object")
        return
    if contract.get("schema_version") != PRODUCTION_CONTRACT_SCHEMA:
        errors.append(f"contracts/production_contract.yaml schema_version must be {PRODUCTION_CONTRACT_SCHEMA}")
    format_contract_profile = contract.get("format_contract_profile")
    if format_contract_profile is not None and not SAFE_METADATA_TOKEN.fullmatch(str(format_contract_profile)):
        errors.append("contracts/production_contract.yaml format_contract_profile must be a safe non-empty slug")
    quality_gate_profile = contract.get("quality_gate_profile")
    if quality_gate_profile is not None and not SAFE_METADATA_TOKEN.fullmatch(str(quality_gate_profile)):
        errors.append("contracts/production_contract.yaml quality_gate_profile must be a safe non-empty slug")
    production_capabilities = contract.get("production_capabilities")
    if production_capabilities is not None:
        if not isinstance(production_capabilities, list) or not all(
            SAFE_METADATA_TOKEN.fullmatch(str(item)) for item in production_capabilities
        ):
            errors.append("contracts/production_contract.yaml production_capabilities must be a list of safe slugs")
    minimum_evidence = contract.get("minimum_evidence_for_release")
    if minimum_evidence is not None and str(minimum_evidence) not in ALLOWED_EVIDENCE_LEVELS:
        errors.append(
            "contracts/production_contract.yaml minimum_evidence_for_release must be one of: "
            + ", ".join(sorted(ALLOWED_EVIDENCE_LEVELS))
        )
    evidence_policy = contract.get("evidence_policy")
    if evidence_policy is not None:
        if not isinstance(evidence_policy, dict):
            errors.append("contracts/production_contract.yaml evidence_policy must be an object")
        else:
            for key in ("metadata_only_release_allowed", "l3_requires_sample_qa"):
                if key in evidence_policy and not isinstance(evidence_policy[key], bool):
                    errors.append(f"contracts/production_contract.yaml evidence_policy.{key} must be a boolean")
            for key in ("visual_claims_require", "motion_audio_claims_require"):
                if key in evidence_policy and str(evidence_policy[key]) not in ALLOWED_EVIDENCE_LEVELS:
                    errors.append(
                        f"contracts/production_contract.yaml evidence_policy.{key} must be one of: "
                        + ", ".join(sorted(ALLOWED_EVIDENCE_LEVELS))
                    )
    required_outputs = contract.get("required_outputs")
    if required_outputs is not None:
        if not isinstance(required_outputs, dict):
            errors.append("contracts/production_contract.yaml required_outputs must be an object")
        else:
            for key, value in required_outputs.items():
                if not SAFE_METADATA_TOKEN.fullmatch(str(key)):
                    errors.append(f"contracts/production_contract.yaml required_outputs key must be a safe slug: {key}")
                if str(value) not in ALLOWED_OUTPUT_REQUIREMENTS:
                    errors.append(
                        "contracts/production_contract.yaml required_outputs values must be one of: "
                        + ", ".join(sorted(ALLOWED_OUTPUT_REQUIREMENTS))
                    )
    modality_contracts = contract.get("modality_contracts")
    if modality_contracts is not None:
        if not isinstance(modality_contracts, dict):
            errors.append("contracts/production_contract.yaml modality_contracts must be an object")
        else:
            for modality, rules in modality_contracts.items():
                if not SAFE_METADATA_TOKEN.fullmatch(str(modality)):
                    errors.append(f"contracts/production_contract.yaml modality_contracts key must be a safe slug: {modality}")
                if not isinstance(rules, dict):
                    errors.append(f"contracts/production_contract.yaml modality_contracts.{modality} must be an object")
                    continue
                for rule_key, rule_value in rules.items():
                    if not SAFE_METADATA_TOKEN.fullmatch(str(rule_key)):
                        errors.append(
                            f"contracts/production_contract.yaml modality_contracts.{modality} rule key must be a safe slug: {rule_key}"
                        )
                    if str(rule_key) == "hook_candidates_min":
                        if not isinstance(rule_value, int) or rule_value < 1:
                            errors.append(
                                "contracts/production_contract.yaml modality_contracts.copy.hook_candidates_min must be an integer >= 1"
                            )
                    elif str(rule_key).endswith(
                        (
                            "_required",
                            "_forbidden",
                            "_audit_required",
                            "_alignment_required",
                            "_review_required",
                        )
                    ) and not isinstance(rule_value, bool):
                        errors.append(
                            f"contracts/production_contract.yaml modality_contracts.{modality}.{rule_key} must be a boolean"
                        )


def _validate_release_gates(root: Path, errors: list[str]) -> None:
    path = root / "quality" / "release_gates.yaml"
    data = _read_yaml(path, errors, {})
    if not isinstance(data, dict):
        errors.append("quality/release_gates.yaml must be an object")
        return
    gates = data.get("gates")
    if not isinstance(gates, list):
        errors.append("quality/release_gates.yaml must contain gates list")
        return
    known_checkers = available_checker_names()
    for index, gate in enumerate(gates):
        if isinstance(gate, str):
            if not gate.strip():
                errors.append(f"quality release gate {index} must not be empty")
            continue
        if not isinstance(gate, dict):
            errors.append(f"quality release gate {index} must be a string id or object binding")
            continue
        gate_id = str(gate.get("id") or "").strip()
        phase = str(gate.get("phase") or "").strip()
        severity = str(gate.get("severity") or "blocker").strip()
        checker = str(gate.get("checker") or "").strip()
        params = gate.get("params", {})
        if not gate_id:
            errors.append(f"quality release gate {index} missing id")
        if not phase:
            errors.append(f"quality release gate {gate_id or index} missing phase")
        elif phase not in ALLOWED_GATE_PHASES:
            errors.append(
                f"quality release gate {gate_id or index} phase must be one of: "
                + ", ".join(sorted(ALLOWED_GATE_PHASES))
            )
        if severity not in ALLOWED_GATE_SEVERITIES:
            errors.append(
                f"quality release gate {gate_id or index} severity must be one of: "
                + ", ".join(sorted(ALLOWED_GATE_SEVERITIES))
            )
        if not checker:
            errors.append(f"quality release gate {gate_id or index} missing checker")
        elif checker not in known_checkers:
            errors.append(f"quality release gate {gate_id or index} unknown checker: {checker}")
        if params is not None and not isinstance(params, dict):
            errors.append(f"quality release gate {gate_id or index} params must be an object")


def _validate_video_elements(runtime: dict[str, Any], errors: list[str]) -> None:
    video_elements = runtime.get("video_elements")
    if video_elements is None:
        errors.append("contracts/runtime.yaml video_elements is required")
        return
    if not isinstance(video_elements, dict):
        errors.append("contracts/runtime.yaml video_elements must be an object")
        return

    for section in sorted(set(video_elements) - ALLOWED_VIDEO_ELEMENT_SECTIONS):
        errors.append(f"contracts/runtime.yaml video_elements has unsupported section: {section}")

    section_keys: dict[str, set[str]] = {}
    for section in ("fixed", "defaults", "user_overridable"):
        value = video_elements.get(section, {})
        if value is None:
            value = {}
        if not isinstance(value, dict):
            errors.append(f"contracts/runtime.yaml video_elements.{section} must be an object")
            continue
        keys: set[str] = set()
        for key, item in value.items():
            key_text = str(key)
            if not SAFE_METADATA_TOKEN.fullmatch(key_text):
                errors.append(f"contracts/runtime.yaml video_elements.{section} key must be a safe slug: {key}")
                continue
            keys.add(key_text)
            if section == "user_overridable" and not (
                isinstance(item, list) and all(str(option).strip() for option in item)
            ):
                errors.append(f"contracts/runtime.yaml video_elements.user_overridable.{key_text} must be a list")
        section_keys[section] = keys

    for left, right in (
        ("fixed", "defaults"),
        ("fixed", "user_overridable"),
        ("defaults", "user_overridable"),
    ):
        for key in sorted(section_keys.get(left, set()) & section_keys.get(right, set())):
            errors.append(f"contracts/runtime.yaml video_elements key appears in both {left} and {right}: {key}")

    forbidden = video_elements.get("forbidden", [])
    if forbidden is None:
        forbidden = []
    if not isinstance(forbidden, list):
        errors.append("contracts/runtime.yaml video_elements.forbidden must be a list")
        return
    for index, item in enumerate(forbidden):
        item_text = str(item)
        if not SAFE_METADATA_TOKEN.fullmatch(item_text):
            errors.append(f"contracts/runtime.yaml video_elements.forbidden[{index}] must be a safe slug")


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
    if MIGRATION_PLACEHOLDER.search(value):
        errors.append(f"migration placeholder found in recipe/package file: {label}")


def check_shareable_text(label: str, value: str, *, allow_artifact_manifest: bool = False) -> list[str]:
    errors: list[str] = []
    _check_string_content(label, value, errors, allow_artifact_manifest=allow_artifact_manifest)
    return errors


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


def _scan_script_surfaces(root: Path, errors: list[str]) -> None:
    scripts_dir = root / "scripts"
    if not scripts_dir.exists():
        return
    for path in sorted(scripts_dir.rglob("*")):
        if path.is_symlink():
            errors.append(f"capsule scripts must not contain symlinks: {path.relative_to(root)}")
            continue
        if not path.is_file() or path.suffix.lower() not in SCRIPT_TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append(f"capsule script text file must be UTF-8: {relative}")
            continue
        if path.suffix.lower() == ".py":
            try:
                ast.parse(text, filename=relative)
            except SyntaxError as exc:
                errors.append(f"invalid Python capsule script {relative}: {exc.msg} at line {exc.lineno}")
        if SCRIPT_SECRET.search(text):
            errors.append(f"secret-looking value in capsule script: {relative}")
        if LOCAL_PATH.search(text):
            errors.append(f"local absolute path found in capsule script: {relative}")


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
    content_scope = _read_yaml(root / "contracts" / "content_scope.yaml", errors, {})
    rules_doc = _read_yaml(root / "quality" / "rules.yaml", errors, {})
    assets_doc = _read_yaml(root / "assets" / "index.yaml", errors, {})

    if not isinstance(capsule, dict):
        errors.append("capsule.yaml must be an object")
        capsule = {}
    if not isinstance(runtime, dict):
        errors.append("contracts/runtime.yaml must be an object")
        runtime = {}
    errors.extend(validate_content_scope_contract(content_scope))
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
    if capsule.get("profile") != VIDEO_OKF_PROFILE:
        errors.append(f"capsule.yaml profile must be {VIDEO_OKF_PROFILE}")
    if not str(capsule.get("primary_workflow") or "").strip():
        errors.append("capsule.yaml primary_workflow must be a non-empty string")
    capabilities = capsule.get("capabilities")
    if not isinstance(capabilities, list) or not any(str(item).strip() for item in capabilities):
        errors.append("capsule.yaml capabilities must be a non-empty list")
    tags = capsule.get("tags")
    if not isinstance(tags, list) or not any(str(item).strip() for item in tags):
        errors.append("capsule.yaml tags must be a non-empty list for routing and fallback substitution")
    format_family = capsule.get("format_family")
    if format_family is not None and not SAFE_METADATA_TOKEN.fullmatch(str(format_family)):
        errors.append("capsule.yaml format_family must be a safe non-empty slug")
    evidence_level_value = capsule.get("evidence_level")
    if evidence_level_value is not None and str(evidence_level_value) not in ALLOWED_EVIDENCE_LEVELS:
        errors.append(
            "capsule.yaml evidence_level must be one of: "
            + ", ".join(sorted(ALLOWED_EVIDENCE_LEVELS))
        )
    production_capabilities = capsule.get("production_capabilities")
    if production_capabilities is not None:
        if not isinstance(production_capabilities, list) or not all(
            SAFE_METADATA_TOKEN.fullmatch(str(item)) for item in production_capabilities
        ):
            errors.append("capsule.yaml production_capabilities must be a list of safe slugs")
    quality_gate_profile = capsule.get("quality_gate_profile")
    if quality_gate_profile is not None and not SAFE_METADATA_TOKEN.fullmatch(str(quality_gate_profile)):
        errors.append("capsule.yaml quality_gate_profile must be a safe non-empty slug")
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
        routing_paths = set(str(item) for item in read_order.get("routing", []) if str(item).strip())
        planning_paths = set(str(item) for item in read_order.get("planning", []) if str(item).strip())
        for required_path in ("index.md", "CARD.md", "contracts/input_schema.yaml"):
            if required_path not in routing_paths:
                errors.append(f"read_order.routing missing required file: {required_path}")
        if "contracts/content_scope.yaml" not in routing_paths:
            errors.append("read_order.routing missing required file: contracts/content_scope.yaml")
        if "contracts/input_schema.yaml" not in planning_paths:
            errors.append("read_order.planning missing required file: contracts/input_schema.yaml")
        if "contracts/content_scope.yaml" not in planning_paths:
            errors.append("read_order.planning missing required file: contracts/content_scope.yaml")
    else:
        errors.append("capsule.yaml read_order must be an object")

    recipes_dir = root / "recipes"
    if recipes_dir.is_dir():
        for recipe in sorted(recipes_dir.glob("*.md")):
            rel_path = recipe.relative_to(root).as_posix()
            if rel_path not in declared_read_order_paths:
                errors.append(f"unreferenced recipe file: {rel_path}")

    execution_mode = str(capsule.get("execution_mode") or "")
    entrypoints = capsule.get("entrypoints") if isinstance(capsule.get("entrypoints"), dict) else {}
    if not isinstance(capsule.get("entrypoints"), dict):
        errors.append("capsule.yaml entrypoints must be an object")
    scripts_dir = root / "scripts"
    script_files = [path for path in scripts_dir.rglob("*") if path.is_file()] if scripts_dir.is_dir() else []
    if execution_mode not in {"preset", "local_script"}:
        errors.append("capsule.yaml execution_mode must be preset or local_script")
    elif execution_mode == "preset":
        if entrypoints.get("local_script"):
            errors.append("preset capsule must not declare entrypoints.local_script")
        if script_files:
            errors.append("preset capsule must not contain files under scripts/")
    else:
        local_script = entrypoints.get("local_script")
        if not local_script:
            errors.append("local_script capsule missing entrypoints.local_script")
        else:
            relative_entry = Path(str(local_script))
            target = (root / relative_entry).resolve()
            if relative_entry.is_absolute() or ".." in relative_entry.parts or not target.is_relative_to(root):
                errors.append(f"local_script entrypoint escapes capsule: {local_script}")
            elif not str(local_script).startswith("scripts/"):
                errors.append(f"local_script entrypoint must be under scripts/: {local_script}")
            elif not target.is_file():
                errors.append(f"local_script entrypoint missing: {local_script}")
            elif target.suffix.lower() != ".py":
                errors.append(f"local_script entrypoint must be a Python file: {local_script}")
            else:
                try:
                    entry_text = target.read_text(encoding="utf-8")
                except UnicodeError:
                    errors.append(f"local_script entrypoint must be UTF-8: {local_script}")
                else:
                    for required_flag in ("--topic", "--params", "--output-dir"):
                        if required_flag not in entry_text:
                            errors.append(
                                f"local_script entrypoint missing required protocol flag {required_flag}: {local_script}"
                            )
        if "local_script" not in {str(item) for item in (capabilities or [])}:
            warnings.append("local_script capsule capabilities should include local_script")

    _validate_markdown_concepts(root, errors)
    _validate_production_contract(root, errors)
    _validate_release_gates(root, errors)

    if not isinstance(runtime.get("roles"), dict):
        errors.append("contracts/runtime.yaml roles must be an object")
    if not isinstance(runtime.get("output_contract"), dict):
        errors.append("contracts/runtime.yaml output_contract must be an object")
    if "defaults" in runtime:
        errors.append("contracts/runtime.yaml defaults is not allowed; use video_elements.defaults/fixed/user_overridable")
    _validate_video_elements(runtime, errors)

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
    _scan_script_surfaces(root, errors)
    for finding in audit_reusable_surfaces(root, content_scope):
        errors.append(
            "episode-specific literal found in reusable capsule surface: "
            f"{finding['path']}: {finding['literal']}"
        )

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
