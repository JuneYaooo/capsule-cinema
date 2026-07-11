from __future__ import annotations

from pathlib import Path

from src.capsule_package_loader import DEFAULT_SEARCH_ROOTS

from .loader import CapsuleLoadError, load_definition
from .result import Issue, ResultEnvelope, failure, success


_DOCTOR_REMEDIATION = "Run the doctor command for package diagnostics."


def _issue_from_load_error(exc: CapsuleLoadError, *, warning: bool = False) -> Issue:
    return Issue(
        code=exc.code,
        message=str(exc),
        severity="warning" if warning else "error",
        subject=exc.subject,
        remediation=_DOCTOR_REMEDIATION,
        details=exc.details,
    )


def discover_capsules(
    search_roots: list[str | Path] | None = None,
) -> ResultEnvelope:
    roots = DEFAULT_SEARCH_ROOTS if search_roots is None else search_roots
    package_paths: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        for candidate in sorted(Path(root).expanduser().glob("*.capsule")):
            if not candidate.is_dir():
                continue
            package = candidate.resolve()
            if package in seen:
                continue
            seen.add(package)
            package_paths.append(package)

    items: list[dict[str, object]] = []
    issues: list[Issue] = []
    for package in package_paths:
        try:
            definition = load_definition(package)
        except CapsuleLoadError as exc:
            issues.append(_issue_from_load_error(exc, warning=True))
            continue
        items.append(definition.public_summary())

    items.sort(key=lambda item: item["name"])
    return success("catalog_ready", {"count": len(items), "capsules": items}, issues)


def show_capsule(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> ResultEnvelope:
    try:
        definition = load_definition(name_or_path, search_roots=search_roots)
    except CapsuleLoadError as exc:
        status = "not_found" if exc.code == "capsule_not_found" else "invalid_capsule"
        return failure(status, [_issue_from_load_error(exc)])
    return success("capsule_ready", {"capsule": definition.public_summary()})
