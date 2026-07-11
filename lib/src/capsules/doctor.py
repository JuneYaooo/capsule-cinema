from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.capsule_package_loader import CapsulePackageError, load_runtime_contract
from src.capsule_preflight import run_preflight, scan_available_env, to_report
from src.capsule_resolver import load_all_tools

from .loader import CapsuleLoadError, load_definition
from .result import Issue, ResultEnvelope, failure, success


_BLOCKED_REMEDIATION = (
    "Configure one of the required local tools or environment keys, "
    "then run doctor again."
)
_INVALID_REMEDIATION = "Fix the capsule package, then run doctor again."


def _invalid_issue(
    code: str,
    message: str,
    subject: str,
    details: dict[str, Any] | None = None,
) -> ResultEnvelope:
    return failure(
        "invalid_capsule",
        [
            Issue(
                code=code,
                message=message,
                subject=subject,
                remediation=_INVALID_REMEDIATION,
                details=details or {},
            )
        ],
    )


def _from_load_error(exc: CapsuleLoadError) -> ResultEnvelope:
    return _invalid_issue(exc.code, str(exc), exc.subject, exc.details)


def doctor_capsule(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
    environ: dict[str, str] | None = None,
    tools: dict[str, Any] | None = None,
) -> ResultEnvelope:
    try:
        definition = load_definition(name_or_path, search_roots=search_roots)
    except CapsuleLoadError as exc:
        return _from_load_error(exc)

    try:
        runtime = load_runtime_contract(name_or_path, search_roots=search_roots)
    except CapsulePackageError:
        return _invalid_issue(
            "invalid_capsule_document",
            "Could not read capsule runtime contract.",
            definition.metadata.source_path,
            {
                "document": str(
                    Path(definition.metadata.source_path) / "contracts" / "runtime.yaml"
                )
            },
        )

    roles = runtime.get("roles", {})
    if not isinstance(roles, dict) or any(
        not isinstance(role_name, str) or not isinstance(role, dict)
        for role_name, role in roles.items()
    ):
        return _invalid_issue(
            "invalid_runtime_contract",
            "Capsule runtime roles must be an object of role objects.",
            definition.metadata.name,
        )

    capsule_summary = definition.public_summary()
    if not roles:
        return success(
            "ready",
            {"capsule": capsule_summary, "preflight": None},
            [
                Issue(
                    code="preflight_not_declared",
                    message=(
                        "Capsule declares no capability roles; "
                        "only package structure was checked."
                    ),
                    severity="info",
                    subject=definition.metadata.name,
                )
            ],
        )

    selected_tools = tools if tools is not None else load_all_tools()
    selected_environ = environ if environ is not None else dict(os.environ)
    output_contract = runtime.get("output_contract")
    capsule = {
        "name": definition.metadata.name,
        "roles": roles,
        "output_contract": output_contract if isinstance(output_contract, dict) else {},
    }
    preflight = run_preflight(
        capsule,
        selected_tools,
        scan_available_env(selected_environ),
    )
    report = to_report(preflight)
    data = {"capsule": capsule_summary, "preflight": report}

    if preflight.status == "ok":
        return success("ready", data)
    if preflight.status == "needs_confirmation":
        return success(
            "needs_confirmation",
            data,
            [
                Issue(
                    code="local_substitution_requires_confirmation",
                    message="Local capability substitutions require confirmation.",
                    severity="warning",
                    subject=definition.metadata.name,
                )
            ],
        )
    if preflight.status == "blocked":
        return failure(
            "blocked",
            [
                Issue(
                    code="local_capability_blocked",
                    message="Required local capabilities are unavailable.",
                    subject=definition.metadata.name,
                    remediation=_BLOCKED_REMEDIATION,
                )
            ],
            data,
        )
    return _invalid_issue(
        "invalid_runtime_contract",
        "Capsule preflight returned an unsupported status.",
        definition.metadata.name,
        {"status": preflight.status},
    )
