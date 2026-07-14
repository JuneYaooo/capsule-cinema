from __future__ import annotations

from pathlib import Path
from typing import Any


CONTENT_SCOPE_SCHEMA = "capsule.content_scope.v1"
SCANNABLE_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py"}
EXCLUDED_PATHS = {"contracts/content_scope.yaml"}
REQUIRED_POLICIES = {
    "allow_series_fixed_defaults": True,
    "forbid_episode_specific_defaults": True,
    "active_recipe_examples_must_use_placeholders": True,
    "current_run_input_may_reuse_literal": True,
}


def default_content_scope_contract() -> dict[str, Any]:
    return {
        "schema_version": CONTENT_SCOPE_SCHEMA,
        "series_fixed": ["format_rules", "reusable_assets"],
        "episode_variable": ["topic", "subject_facts", "evidence_claims", "episode_copy"],
        "forbidden_reusable_literals": [],
        "policies": dict(REQUIRED_POLICIES),
    }


def validate_content_scope_contract(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["contracts/content_scope.yaml must be an object"]
    if value.get("schema_version") != CONTENT_SCOPE_SCHEMA:
        errors.append(f"contracts/content_scope.yaml schema_version must be {CONTENT_SCOPE_SCHEMA}")
    for field in ("series_fixed", "episode_variable", "forbidden_reusable_literals"):
        items = value.get(field)
        if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
            errors.append(f"contracts/content_scope.yaml {field} must be a list of non-empty strings")
    if isinstance(value.get("series_fixed"), list) and not value["series_fixed"]:
        errors.append("contracts/content_scope.yaml series_fixed must declare at least one series-level element")
    if isinstance(value.get("episode_variable"), list) and not value["episode_variable"]:
        errors.append("contracts/content_scope.yaml episode_variable must declare at least one per-run element")
    policies = value.get("policies")
    if not isinstance(policies, dict):
        errors.append("contracts/content_scope.yaml policies must be an object")
    else:
        for key, expected in REQUIRED_POLICIES.items():
            if policies.get(key) is not expected:
                errors.append(f"contracts/content_scope.yaml policies.{key} must be {str(expected).lower()}")
    literals = value.get("forbidden_reusable_literals")
    if isinstance(literals, list):
        normalized = [str(item).strip().casefold() for item in literals]
        if len(normalized) != len(set(normalized)):
            errors.append("contracts/content_scope.yaml forbidden_reusable_literals must not contain duplicates")
    return errors


def audit_reusable_surfaces(capsule_dir: str | Path, contract: Any) -> list[dict[str, str]]:
    if not isinstance(contract, dict):
        return []
    literals = [
        str(item).strip()
        for item in contract.get("forbidden_reusable_literals", [])
        if isinstance(item, str) and item.strip()
    ]
    if not literals:
        return []

    root = Path(capsule_dir).resolve()
    findings: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCANNABLE_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDED_PATHS or relative.startswith("examples/") or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        folded = text.casefold()
        for literal in literals:
            if literal.casefold() in folded:
                findings.append({"path": relative, "literal": literal})
    return findings
