from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_EVIDENCE_SCHEMA = "capsule.local_script_evidence.v1"
EXECUTION_MODES = {"preset", "local_script", "review_required"}


class CapsuleScriptPolicyError(ValueError):
    """Raised when a proposed local script is not proven reusable yet."""


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        values = []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def load_script_evidence(value: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    text = str(value).strip()
    if not text:
        return {}
    if text.startswith("{"):
        payload = json.loads(text)
    else:
        payload = json.loads(Path(text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CapsuleScriptPolicyError("local-script evidence must be a JSON object")
    return payload


def script_evidence_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["local-script evidence must be an object"]
    errors: list[str] = []
    schema = str(value.get("schema_version") or SCRIPT_EVIDENCE_SCHEMA).strip()
    if schema != SCRIPT_EVIDENCE_SCHEMA:
        errors.append(f"local-script evidence schema_version must be {SCRIPT_EVIDENCE_SCHEMA}")
    successful_runs = value.get("successful_runs")
    if not isinstance(successful_runs, int) or isinstance(successful_runs, bool) or successful_runs < 1:
        errors.append("local-script evidence successful_runs must be an integer >= 1")
    if value.get("cross_topic_verified") is not True:
        errors.append("local-script evidence cross_topic_verified must be true")
    if not _strings(value.get("deterministic_steps")):
        errors.append("local-script evidence deterministic_steps must be a non-empty list")
    if not _strings(value.get("parameterized_inputs")):
        errors.append("local-script evidence parameterized_inputs must be a non-empty list")
    return errors


def normalize_script_evidence(value: Any) -> dict[str, Any]:
    errors = script_evidence_errors(value)
    if errors:
        raise CapsuleScriptPolicyError("; ".join(errors))
    return {
        "schema_version": SCRIPT_EVIDENCE_SCHEMA,
        "successful_runs": int(value["successful_runs"]),
        "cross_topic_verified": True,
        "deterministic_steps": _strings(value.get("deterministic_steps")),
        "parameterized_inputs": _strings(value.get("parameterized_inputs")),
    }


def normalize_execution_strategy(value: Any) -> tuple[dict[str, Any], list[str]]:
    source = dict(value) if isinstance(value, dict) else {}
    requested_mode = str(source.get("mode") or "preset").strip()
    warnings: list[str] = []
    if requested_mode not in EXECUTION_MODES:
        warnings.append(
            f"Analyzer returned unsupported execution strategy {requested_mode!r}; manual review is required."
        )
        requested_mode = "review_required"

    deterministic_steps = _strings(source.get("deterministic_steps"))
    parameterized_inputs = _strings(source.get("parameterized_inputs"))
    episode_specific_values = _strings(source.get("episode_specific_values"))
    evidence_source = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    evidence = {
        "schema_version": SCRIPT_EVIDENCE_SCHEMA,
        "successful_runs": evidence_source.get("successful_runs", 0),
        "cross_topic_verified": evidence_source.get("cross_topic_verified") is True,
        "deterministic_steps": deterministic_steps,
        "parameterized_inputs": parameterized_inputs,
    }

    mode = requested_mode
    review_reasons: list[str] = []
    if requested_mode == "local_script":
        review_reasons = script_evidence_errors(evidence)
        if review_reasons:
            mode = "review_required"
            warnings.append(
                "Analyzer suggested local_script without sufficient reusable evidence; "
                "the draft was downgraded to review_required."
            )

    return (
        {
            "mode": mode,
            "requested_mode": requested_mode,
            "reason": str(source.get("reason") or "").strip(),
            "deterministic_steps": deterministic_steps,
            "parameterized_inputs": parameterized_inputs,
            "episode_specific_values": episode_specific_values,
            "evidence": {
                "successful_runs": evidence["successful_runs"],
                "cross_topic_verified": evidence["cross_topic_verified"],
            },
            "review_reasons": review_reasons,
        },
        warnings,
    )


def evidence_from_execution_strategy(strategy: Any) -> dict[str, Any]:
    source = strategy if isinstance(strategy, dict) else {}
    evidence = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    return normalize_script_evidence(
        {
            "schema_version": SCRIPT_EVIDENCE_SCHEMA,
            "successful_runs": evidence.get("successful_runs"),
            "cross_topic_verified": evidence.get("cross_topic_verified"),
            "deterministic_steps": source.get("deterministic_steps"),
            "parameterized_inputs": source.get("parameterized_inputs"),
        }
    )
