"""Small executable gate runner for capsule release/preflight checks.

This intentionally stays below a full DSL: gates name a known checker plus
simple params. Unknown structured checkers fail closed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml


GATE_REPORT_SCHEMA = "capsule_cinema.capsule_gate_report.v1"


def _read_yaml(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return yaml.safe_load(path.read_text(encoding="utf-8")) or fallback


def _structured_gates(capsule_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(capsule_dir).expanduser()
    data = _read_yaml(root / "quality" / "release_gates.yaml", {})
    gates = data.get("gates") if isinstance(data, dict) else None
    if not isinstance(gates, list):
        return []
    return [gate for gate in gates if isinstance(gate, dict)]


def load_gate_bindings(capsule_dir: str | Path) -> list[dict[str, Any]]:
    """Load object-form release gate bindings.

    Existing string-only gates are intentionally ignored here for backwards
    compatibility; the package validator still verifies their structure.
    """
    return _structured_gates(capsule_dir)


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _path_tokens(path: str) -> list[tuple[str, bool]]:
    tokens: list[tuple[str, bool]] = []
    for raw in str(path or "").split("."):
        if not raw:
            continue
        if raw.endswith("[]"):
            tokens.append((raw[:-2], True))
        else:
            tokens.append((raw, False))
    return tokens


def _path_values(payload: Any, path: str) -> list[tuple[str, Any]]:
    tokens = _path_tokens(path)
    current: list[tuple[str, Any]] = [("", payload)]
    for key, each in tokens:
        next_values: list[tuple[str, Any]] = []
        for prefix, value in current:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            child_path = f"{prefix}.{key}" if prefix else key
            if each:
                if isinstance(child, list):
                    for index, item in enumerate(child):
                        next_values.append((f"{child_path}[{index}]", item))
                continue
            next_values.append((child_path, child))
        current = next_values
    return current


def _first_list_from_payloads(path: str, *payloads: dict[str, Any] | None) -> tuple[str, list[Any]] | None:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for resolved_path, value in _path_values(payload, path):
            if isinstance(value, list):
                return resolved_path, value
    return None


def _first_values_from_payloads(
    path: str,
    *payloads: dict[str, Any] | None,
) -> list[tuple[str, Any]] | None:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        values = _path_values(payload, path)
        if values:
            return values
    return None


def _issue(path: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"path": path, "message": message, **extra}


def check_forbidden_profile_fields(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del manifest, release
    payload = profile if isinstance(profile, dict) else {}
    issues: list[dict[str, Any]] = []
    fields = params.get("fields") if isinstance(params.get("fields"), list) else []
    for field in fields:
        for path, value in _path_values(payload, str(field)):
            if _is_non_empty(value):
                issues.append(_issue(path, "field must be empty or absent", value=value))
    return issues


def check_list_length_between(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del manifest, release
    payload = profile if isinstance(profile, dict) else {}
    path = str(params.get("path") or "")
    minimum = int(params.get("min", 0))
    maximum = int(params.get("max", minimum))
    values = _path_values(payload, path)
    if not values:
        return [_issue(path, "list is missing", actual=None, expected={"min": minimum, "max": maximum})]
    issues: list[dict[str, Any]] = []
    for resolved_path, value in values:
        actual = len(value) if isinstance(value, list) else None
        if actual is None or actual < minimum or actual > maximum:
            issues.append(
                _issue(
                    resolved_path,
                    "list length is outside allowed range",
                    actual=actual,
                    expected={"min": minimum, "max": maximum},
                )
            )
    return issues


def check_manifest_item_flags(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del release
    manifest_path = str(params.get("manifest_path") or "")
    required = params.get("require") if isinstance(params.get("require"), dict) else {}
    found = _first_list_from_payloads(manifest_path, profile, manifest)
    if found is None:
        return [_issue(manifest_path, "manifest list is missing")]
    base_path, items = found
    issues: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(_issue(f"{base_path}[{index}]", "manifest item must be an object"))
            continue
        for key, expected in required.items():
            actual = item.get(key)
            if actual != expected:
                issues.append(
                    _issue(
                        f"{base_path}[{index}].{key}",
                        "manifest item flag does not match required value",
                        actual=actual,
                        expected=expected,
                    )
                )
    return issues


def check_path_value_equals(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    path = str(params.get("path") or "")
    expected = params.get("expected")
    values = _first_values_from_payloads(path, release, manifest, profile)
    if values is None:
        return [_issue(path, "value is missing", actual=None, expected=expected)]
    issues: list[dict[str, Any]] = []
    for resolved_path, actual in values:
        if actual != expected:
            issues.append(
                _issue(
                    resolved_path,
                    "value does not match required value",
                    actual=actual,
                    expected=expected,
                )
            )
    return issues


def check_number_between(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    path = str(params.get("path") or "")
    try:
        minimum = float(params.get("min"))
        maximum = float(params.get("max"))
    except (TypeError, ValueError):
        return [_issue(path, "gate min and max must be numbers", actual={"min": params.get("min"), "max": params.get("max")})]
    if minimum > maximum:
        return [_issue(path, "gate min must not exceed max", actual={"min": minimum, "max": maximum})]
    values = _first_values_from_payloads(path, release, manifest, profile)
    expected = {"min": minimum, "max": maximum}
    if values is None:
        return [_issue(path, "number is missing", actual=None, expected=expected)]
    issues: list[dict[str, Any]] = []
    for resolved_path, actual in values:
        is_number = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        if not is_number or float(actual) < minimum or float(actual) > maximum:
            issues.append(
                _issue(
                    resolved_path,
                    "number is outside allowed range",
                    actual=actual,
                    expected=expected,
                )
            )
    return issues


def check_path_non_empty(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    path = str(params.get("path") or "")
    values = _first_values_from_payloads(path, release, manifest, profile)
    if values is None:
        return [_issue(path, "value is missing or empty", actual=None)]
    issues: list[dict[str, Any]] = []
    for resolved_path, actual in values:
        if not _is_non_empty(actual):
            issues.append(_issue(resolved_path, "value is missing or empty", actual=actual))
    return issues


def _contains_marker(value: Any, markers: set[str]) -> bool:
    if isinstance(value, str):
        return value in markers
    if isinstance(value, dict):
        return any(_contains_marker(item, markers) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item, markers) for item in value)
    return False


def check_fallback_blocks_approved_release(
    params: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    markers = {str(item) for item in params.get("fallback_markers", []) if str(item)}
    allowed_status = {str(item) for item in params.get("allowed_release_status", []) if str(item)}
    has_fallback = any(_contains_marker(payload, markers) for payload in (profile, manifest, release))
    if not has_fallback:
        return []
    status = ""
    for payload in (release, manifest, profile):
        if isinstance(payload, dict):
            status = str(payload.get("status") or payload.get("release_status") or "").strip()
            if status:
                break
    if status in allowed_status:
        return []
    return [
        _issue(
            "release.status",
            "fallback marker cannot be approved for this release status",
            actual=status,
            expected=sorted(allowed_status),
        )
    ]


CHECKERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "forbidden_profile_fields": check_forbidden_profile_fields,
    "list_length_between": check_list_length_between,
    "manifest_item_flags": check_manifest_item_flags,
    "path_value_equals": check_path_value_equals,
    "number_between": check_number_between,
    "path_non_empty": check_path_non_empty,
    "fallback_blocks_approved_release": check_fallback_blocks_approved_release,
}


def available_checker_names() -> set[str]:
    return set(CHECKERS)


def _gate_matches_phase(gate: dict[str, Any], phase: str) -> bool:
    gate_phase = str(gate.get("phase") or "").strip()
    return gate_phase == phase


def _check_result(
    gate: dict[str, Any],
    ok: bool,
    *,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(gate.get("id") or ""),
        "ok": ok,
        "severity": str(gate.get("severity") or "blocker"),
        "phase": str(gate.get("phase") or ""),
        "checker": str(gate.get("checker") or ""),
        "detail": detail or {},
    }


def run_capsule_gates(
    capsule_dir: str | Path,
    phase: str,
    *,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for gate in load_gate_bindings(capsule_dir):
        if not _gate_matches_phase(gate, phase):
            continue
        checker_name = str(gate.get("checker") or "").strip()
        checker = CHECKERS.get(checker_name)
        if checker is None:
            checks.append(_check_result(gate, False, detail={"message": "unknown gate checker"}))
            continue
        params = gate.get("params") if isinstance(gate.get("params"), dict) else {}
        issues = checker(params, profile=profile, manifest=manifest, release=release)
        if not issues:
            checks.append(_check_result(gate, True))
            continue
        for issue in issues:
            checks.append(_check_result(gate, False, detail=issue))

    blockers = [
        check["id"]
        for check in checks
        if not check.get("ok") and str(check.get("severity") or "blocker") == "blocker"
    ]
    unique_blockers = list(dict.fromkeys(blockers))
    warning_ids = [
        check["id"]
        for check in checks
        if not check.get("ok") and str(check.get("severity") or "blocker") != "blocker"
    ]
    return {
        "schema": GATE_REPORT_SCHEMA,
        "capsule_dir": str(Path(capsule_dir).expanduser().resolve()),
        "phase": phase,
        "ok": not unique_blockers,
        "status": "blocked" if unique_blockers else "pass",
        "blockers": unique_blockers,
        "warnings": list(dict.fromkeys(warning_ids)),
        "checks": checks,
    }
