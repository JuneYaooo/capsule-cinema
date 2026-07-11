from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

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

# Keep these tool-schema fields synchronized with capsule_resolver's reads.
_RESOLVER_STRING_LIST_FIELDS = ("requires_env", "tags")
_RESOLVER_ENV_GROUP_FIELD = "requires_env_any"


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


def _runtime_roles_are_valid(roles: dict[str, Any]) -> bool:
    list_fields = ("depends_on", "requires", "forbids", "prefers")
    mapping_fields = ("requires_enums", "requires_limits", "prefers_enums")
    return all(
        all(
            field not in role
            or (
                isinstance(role[field], list)
                and all(type(item) is str for item in role[field])
            )
            for field in list_fields
        )
        and all(
            field not in role
            or (
                isinstance(role[field], Mapping)
                and all(type(key) is str for key in role[field])
            )
            for field in mapping_fields
        )
        for role in roles.values()
    )


def _tools_are_valid(tools: Any) -> bool:
    if not isinstance(tools, Mapping):
        return False
    for name, tool in tools.items():
        if type(name) is not str or not isinstance(tool, Mapping):
            return False
        for field in _RESOLVER_STRING_LIST_FIELDS:
            if field in tool and (
                not isinstance(tool[field], list)
                or not all(type(item) is str for item in tool[field])
            ):
                return False
        if _RESOLVER_ENV_GROUP_FIELD in tool:
            groups = tool[_RESOLVER_ENV_GROUP_FIELD]
            if not isinstance(groups, list) or any(
                not isinstance(group, list)
                or not all(type(key) is str for key in group)
                for group in groups
            ):
                return False
        provides = tool.get("provides", {})
        if not isinstance(provides, Mapping):
            return False
        for field in ("flags", "enums"):
            values = provides.get(field, {})
            if not isinstance(values, Mapping) or not all(
                type(key) is str for key in values
            ):
                return False
        limits = provides.get("limits", {})
        if not isinstance(limits, Mapping) or any(
            type(key) is not str or not isinstance(values, list)
            for key, values in limits.items()
        ):
            return False
        if "cost_tier" in tool and type(tool["cost_tier"]) is not str:
            return False
    return True


def _tool_shape_failure(code: str, message: str, subject: str) -> ResultEnvelope:
    return failure(
        "blocked",
        [
            Issue(
                code=code,
                message=message,
                subject=subject,
                remediation=_BLOCKED_REMEDIATION,
            )
        ],
    )


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
    except (CapsulePackageError, OSError, UnicodeError):
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
    if not _runtime_roles_are_valid(roles):
        return _invalid_issue(
            "invalid_runtime_contract",
            "Capsule runtime role fields have invalid types.",
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

    if tools is None:
        try:
            selected_tools = load_all_tools()
        except (
            AttributeError,
            OSError,
            TypeError,
            UnicodeError,
            yaml.YAMLError,
        ):
            return _tool_shape_failure(
                "local_tool_catalog_unavailable",
                "Could not read local tool capability catalog.",
                definition.metadata.name,
            )
        if not _tools_are_valid(selected_tools):
            return _tool_shape_failure(
                "local_tool_catalog_unavailable",
                "Could not read local tool capability catalog.",
                definition.metadata.name,
            )
    else:
        selected_tools = tools
        if not _tools_are_valid(selected_tools):
            return _tool_shape_failure(
                "invalid_tools_argument",
                "Injected tools must be a mapping of tool mappings.",
                definition.metadata.name,
            )
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
