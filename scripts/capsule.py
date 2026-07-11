#!/usr/bin/env python3
"""Unified JSON CLI for discovering, inspecting, and running capsules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT / "lib", PROJECT_ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from src.capsules.catalog import discover_capsules, show_capsule  # noqa: E402
from src.capsules.dispatch import (  # noqa: E402
    DispatchError,
    build_dispatch_plan,
    execute_dispatch_plan,
)
from src.capsules.doctor import doctor_capsule  # noqa: E402
from src.capsules.loader import CapsuleLoadError  # noqa: E402
from src.capsules.result import Issue, ResultEnvelope, failure, success  # noqa: E402


_RUNNER_MARKERS = {"local_script", "local-script"}


def add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--output-dir", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover, inspect, diagnose, plan, and run capsule packages."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="List available capsules.")
    list_parser.add_argument("--root", action="append")

    show_parser = commands.add_parser("show", help="Show a capsule summary.")
    show_parser.add_argument("name")
    show_parser.add_argument("--root", action="append")

    doctor_parser = commands.add_parser("doctor", help="Diagnose a capsule.")
    doctor_parser.add_argument("name")
    doctor_parser.add_argument("--root", action="append")

    plan_parser = commands.add_parser("plan", help="Preview capsule dispatch.")
    add_execution_arguments(plan_parser)

    run_parser = commands.add_parser("run", help="Run a capsule.")
    add_execution_arguments(run_parser)
    return parser


def _invalid_params_result(name: str) -> ResultEnvelope:
    return failure(
        "invalid_request",
        [
            Issue(
                code="invalid_params_json",
                message="--params-json must be a JSON object.",
                subject=name,
                remediation="Pass an object such as --params-json '{}'.",
            )
        ],
    )


def _decode_params(raw: str, name: str) -> tuple[dict[str, Any] | None, ResultEnvelope | None]:
    try:
        params = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, _invalid_params_result(name)
    if not isinstance(params, dict):
        return None, _invalid_params_result(name)
    return params, None


def _from_load_error(exc: CapsuleLoadError) -> ResultEnvelope:
    status = "not_found" if exc.code == "capsule_not_found" else "invalid_capsule"
    return failure(
        status,
        [
            Issue(
                code=exc.code,
                message=str(exc),
                subject=exc.subject,
                remediation="Run the doctor command for package diagnostics.",
                details=exc.details,
            )
        ],
    )


def _from_dispatch_error(exc: DispatchError, subject: str) -> ResultEnvelope:
    return failure(
        "invalid_request",
        [
            Issue(
                code=exc.code,
                message=str(exc),
                subject=subject,
                remediation="Correct the request parameters and retry.",
                details=exc.details,
            )
        ],
    )


def _redact_runner_markers(result: ResultEnvelope) -> ResultEnvelope:
    redacted = result.model_copy(deep=True)
    summary = redacted.data.get("capsule")
    if not isinstance(summary, dict):
        return redacted
    for field in ("capabilities", "tags", "when_to_use", "when_not_to_use"):
        values = summary.get(field)
        if isinstance(values, list):
            summary[field] = [value for value in values if value not in _RUNNER_MARKERS]
    return redacted


def _execute(args: argparse.Namespace) -> ResultEnvelope:
    if args.command == "list":
        return discover_capsules(args.root)
    if args.command == "show":
        return _redact_runner_markers(show_capsule(args.name, args.root))
    if args.command == "doctor":
        return doctor_capsule(args.name, args.root)

    params, invalid = _decode_params(args.params_json, args.name)
    if invalid is not None:
        return invalid
    assert params is not None

    action = args.command
    try:
        plan = build_dispatch_plan(
            args.name,
            args.topic,
            params,
            args.output_dir,
            action,
        )
    except CapsuleLoadError as exc:
        return _from_load_error(exc)
    except DispatchError as exc:
        return _from_dispatch_error(exc, args.name)

    if action == "plan":
        return success(
            "dispatch_ready",
            {
                "capsule": plan.capsule,
                "action": "plan",
                "output_dir": plan.output_dir,
            },
        )
    return execute_dispatch_plan(plan)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = _execute(args)
    print(result.model_dump_json(indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
