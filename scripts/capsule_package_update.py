#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from capsule_package_create import (
    render_card_markdown,
    render_index_markdown,
)
from capsule_package_validate import validate_capsule_dir

KNOWN_RECIPE_DOMAINS = {"structure", "copy", "visual", "audio", "motion"}
TERM_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class CapsuleUpdateConflictError(SystemExit):
    def __init__(self, message: str, conflicts: list[dict[str, Any]]) -> None:
        self.conflicts = conflicts
        super().__init__(message)


def _read_yaml(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return yaml.safe_load(path.read_text(encoding="utf-8")) or fallback


def _dump_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _dedupe_append(existing: list[Any], additions: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in [*existing, *(additions or [])]:
        value = str(item).strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _term_tokens(value: Any) -> set[str]:
    return {match.group(0).lower() for match in TERM_TOKEN.finditer(str(value).replace("_", "-"))}


def _term_conflicts_with_text(proposed: Any, existing: Any) -> bool:
    proposed_tokens = _term_tokens(proposed)
    existing_tokens = _term_tokens(existing)
    return bool(proposed_tokens) and proposed_tokens.issubset(existing_tokens)


def _card_when_not_to_use_lines(root: Path) -> list[str]:
    card_path = root / "CARD.md"
    if not card_path.exists():
        return []
    lines = card_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower() == "## when not to use"
            continue
        if in_section and stripped.startswith("- "):
            result.append(stripped[2:].strip())
    return result


def _when_not_to_use_text(root: Path, capsule: dict[str, Any]) -> list[str]:
    return [*_as_list(capsule.get("when_not_to_use")), *_card_when_not_to_use_lines(root)]


def _flatten_read_order(capsule: dict[str, Any]) -> set[str]:
    read_order = capsule.get("read_order") if isinstance(capsule.get("read_order"), dict) else {}
    paths: set[str] = set()
    for values in read_order.values():
        if not isinstance(values, list):
            continue
        for item in values:
            value = str(item).strip()
            if value:
                paths.add(value)
    return paths


def _conflict(
    conflicts: list[dict[str, Any]],
    *,
    kind: str,
    field: str,
    message: str,
    current: Any,
    proposed: Any,
) -> None:
    conflicts.append(
        {
            "id": f"capsule_update_conflict_{len(conflicts) + 1}",
            "kind": kind,
            "field": field,
            "message": message,
            "current": current,
            "proposed": proposed,
            "requires_user_resolution": True,
        }
    )


def _forbidden_reusable_literals(root: Path) -> list[str]:
    contract = _read_yaml(root / "contracts" / "content_scope.yaml", {})
    if not isinstance(contract, dict):
        return []
    return [
        str(value).strip()
        for value in contract.get("forbidden_reusable_literals", [])
        if isinstance(value, str) and value.strip()
    ]


def _reusable_update_values(
    *,
    display_name: str | None,
    summary: str | None,
    category: str | None,
    primary_workflow: str | None,
    add_capabilities: list[str] | None,
    add_tags: list[str] | None,
    lesson: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for field, value in (
        ("display_name", display_name),
        ("summary", summary),
        ("category", category),
        ("primary_workflow", primary_workflow),
    ):
        if value is not None:
            values.append((field, str(value)))
    values.extend(("add_capability", str(value)) for value in (add_capabilities or []))
    values.extend(("add_tag", str(value)) for value in (add_tags or []))
    if lesson is not None:
        normalized = _normalize_lesson(lesson)
        values.append(("lesson.rule", normalized["rule"]))
        for key in ("applies_when", "promote_to", "avoid"):
            values.extend((f"lesson.{key}", str(value)) for value in normalized.get(key) or [])
    return values


def _find_update_conflicts(
    root: Path,
    capsule: dict[str, Any],
    *,
    display_name: str | None = None,
    summary: str | None = None,
    category: str | None = None,
    primary_workflow: str | None = None,
    add_capabilities: list[str] | None = None,
    add_tags: list[str] | None = None,
    lesson: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    declared_paths = _flatten_read_order(capsule)
    prohibited_texts = _when_not_to_use_text(root, capsule)
    for field, proposed in _reusable_update_values(
        display_name=display_name,
        summary=summary,
        category=category,
        primary_workflow=primary_workflow,
        add_capabilities=add_capabilities,
        add_tags=add_tags,
        lesson=lesson,
    ):
        proposed_folded = proposed.casefold()
        for literal in _forbidden_reusable_literals(root):
            if literal.casefold() not in proposed_folded:
                continue
            _conflict(
                conflicts,
                kind="episode_specific_literal_in_reusable_update",
                field=field,
                message=(
                    "proposed update contains a literal classified as episode-specific; "
                    "generalize the text or reclassify the literal in contracts/content_scope.yaml first"
                ),
                current={"forbidden_reusable_literal": literal},
                proposed=proposed,
            )
    proposed_terms: list[tuple[str, str]] = []
    if summary is not None:
        proposed_terms.append(("summary", summary))
    if category is not None:
        proposed_terms.append(("category", category))
    if primary_workflow is not None:
        proposed_terms.append(("primary_workflow", primary_workflow))
    proposed_terms.extend(("add_capability", value) for value in (add_capabilities or []))
    proposed_terms.extend(("add_tag", value) for value in (add_tags or []))
    for field, proposed in proposed_terms:
        for existing in prohibited_texts:
            if _term_conflicts_with_text(proposed, existing):
                _conflict(
                    conflicts,
                    kind="proposed_value_conflicts_with_when_not_to_use",
                    field=field,
                    message="proposed update overlaps with the capsule's when_not_to_use boundary",
                    current=existing,
                    proposed=proposed,
                )

    if lesson is not None:
        normalized = _normalize_lesson(lesson)
        for avoided in normalized.get("avoid") or []:
            for field in ("applies_when", "promote_to"):
                for proposed in normalized.get(field) or []:
                    if _term_conflicts_with_text(avoided, proposed) or _term_conflicts_with_text(proposed, avoided):
                        _conflict(
                            conflicts,
                            kind="lesson_avoid_overlaps_positive_condition",
                            field=f"lesson.{field}",
                            message="proposed lesson avoids the same condition that it applies to or promotes",
                            current={"avoid": avoided},
                            proposed=proposed,
                        )
            if _term_conflicts_with_text(avoided, normalized.get("rule", "")):
                _conflict(
                    conflicts,
                    kind="lesson_avoid_overlaps_rule",
                    field="lesson.rule",
                    message="proposed lesson rule uses a condition that the lesson also says to avoid",
                    current={"avoid": avoided},
                    proposed=normalized.get("rule", ""),
                )

        for target in normalized.get("promote_to") or []:
            if target not in declared_paths:
                _conflict(
                    conflicts,
                    kind="undeclared_promotion_target",
                    field="lesson.promote_to",
                    message="proposed lesson promotes into a file that is not declared in capsule.yaml read_order",
                    current=sorted(declared_paths),
                    proposed=target,
                )

        scope = normalized.get("scope", "")
        has_scope_surface = scope in KNOWN_RECIPE_DOMAINS and (root / "recipes" / f"{scope}.md").is_file()
        if scope not in KNOWN_RECIPE_DOMAINS and not has_scope_surface:
            _conflict(
                conflicts,
                kind="unknown_lesson_scope",
                field="lesson.scope",
                message="proposed lesson scope has no matching known recipe domain or package surface",
                current=sorted(KNOWN_RECIPE_DOMAINS),
                proposed=scope,
            )

    return conflicts


def _format_conflict_block(conflicts: list[dict[str, Any]]) -> str:
    ids = ", ".join(conflict["id"] for conflict in conflicts)
    return f"capsule update conflicts require user resolution: {ids}"


def _load_conflict_resolution(raw: dict[str, Any] | str | Path | None) -> dict[str, str]:
    if raw is None:
        return {}
    payload: Any
    if isinstance(raw, dict):
        payload = raw
    else:
        text = str(raw).strip()
        if not text:
            return {}
        if text.startswith("{"):
            payload = json.loads(text)
        else:
            payload = json.loads(Path(text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("conflict resolution must be a JSON object")
    entries = payload.get("resolved_conflicts")
    if not isinstance(entries, list):
        raise SystemExit("conflict resolution must contain resolved_conflicts list")
    resolutions: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("each resolved conflict must be an object")
        conflict_id = str(entry.get("id") or "").strip()
        resolution = str(entry.get("resolution") or "").strip()
        if not conflict_id or not resolution:
            raise SystemExit("each resolved conflict must include non-empty id and resolution")
        resolutions[conflict_id] = resolution
    return resolutions


def _ensure_conflicts_resolved(conflicts: list[dict[str, Any]], resolutions: dict[str, str]) -> list[str]:
    if not conflicts:
        return []
    scope_conflicts = [
        conflict["id"]
        for conflict in conflicts
        if conflict.get("kind") == "episode_specific_literal_in_reusable_update"
    ]
    if scope_conflicts:
        raise CapsuleUpdateConflictError(
            "episode-specific reusable update is blocked until content scope is corrected: "
            + ", ".join(scope_conflicts),
            conflicts,
        )
    missing = [conflict["id"] for conflict in conflicts if not resolutions.get(conflict["id"])]
    if missing:
        raise CapsuleUpdateConflictError(
            "unresolved capsule update conflicts: " + ", ".join(missing),
            conflicts,
        )
    return [conflict["id"] for conflict in conflicts]


def _snapshot_package(capsule_dir: Path) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    backup = Path(tmp.name) / "capsule"
    shutil.copytree(capsule_dir, backup)
    return tmp


def _restore_package(capsule_dir: Path, snapshot: tempfile.TemporaryDirectory) -> None:
    backup = Path(snapshot.name) / "capsule"
    if capsule_dir.exists():
        shutil.rmtree(capsule_dir)
    shutil.copytree(backup, capsule_dir)


def _normalize_lesson(lesson: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(lesson, dict):
        raise SystemExit("lesson must be an object")
    required = ("id", "scope", "rule")
    for key in required:
        if not str(lesson.get(key) or "").strip():
            raise SystemExit(f"lesson missing required field: {key}")
    normalized = {
        "id": str(lesson["id"]).strip(),
        "scope": str(lesson["scope"]).strip(),
        "content_scope": str(lesson.get("content_scope") or "series").strip(),
        "rule": str(lesson["rule"]).strip(),
    }
    if normalized["content_scope"] != "series":
        raise SystemExit("promoted lesson content_scope must be series")
    for key in ("applies_when", "promote_to", "avoid"):
        values = lesson.get(key) or []
        if isinstance(values, str):
            values = [values]
        normalized[key] = _dedupe_append([], [str(item) for item in values])
    return normalized


def _upsert_lesson(capsule_dir: Path, lesson: dict[str, Any]) -> None:
    path = capsule_dir / "learning" / "promoted_lessons.yaml"
    doc = _read_yaml(path, {})
    lessons = doc.get("lessons") if isinstance(doc, dict) else None
    if not isinstance(lessons, list):
        lessons = []
    normalized = _normalize_lesson(lesson)
    next_lessons = [item for item in lessons if not (isinstance(item, dict) and item.get("id") == normalized["id"])]
    next_lessons.append(normalized)
    _dump_yaml(path, {"lessons": next_lessons})


def _refresh_markdown_entrypoints(capsule_dir: Path, capsule: dict[str, Any]) -> None:
    _write_text(capsule_dir / "index.md", render_index_markdown(capsule))
    _write_text(capsule_dir / "CARD.md", render_card_markdown(capsule))


def update_capsule_package(
    capsule_dir: str | Path,
    *,
    display_name: str | None = None,
    summary: str | None = None,
    category: str | None = None,
    status: str | None = None,
    primary_workflow: str | None = None,
    add_capabilities: list[str] | None = None,
    add_tags: list[str] | None = None,
    lesson: dict[str, Any] | None = None,
    conflict_resolution: dict[str, Any] | str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(capsule_dir).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"capsule package not found: {root}")
    snapshot = _snapshot_package(root)
    try:
        capsule_path = root / "capsule.yaml"
        capsule = _read_yaml(capsule_path, {})
        if not isinstance(capsule, dict):
            raise SystemExit("capsule.yaml must be an object")

        conflicts = _find_update_conflicts(
            root,
            capsule,
            display_name=display_name,
            summary=summary,
            category=category,
            primary_workflow=primary_workflow,
            add_capabilities=add_capabilities,
            add_tags=add_tags,
            lesson=lesson,
        )
        resolutions = _load_conflict_resolution(conflict_resolution)
        if conflicts and conflict_resolution is None:
            raise CapsuleUpdateConflictError(_format_conflict_block(conflicts), conflicts)
        resolved_conflicts = _ensure_conflicts_resolved(conflicts, resolutions)

        if display_name is not None:
            capsule["display_name"] = str(display_name).strip()
        if summary is not None:
            capsule["summary"] = str(summary).strip()
        if category is not None:
            capsule["category"] = str(category).strip()
        if status is not None:
            capsule["status"] = str(status).strip()
        if primary_workflow is not None:
            capsule["primary_workflow"] = str(primary_workflow).strip()
        if add_capabilities:
            capsule["capabilities"] = _dedupe_append(capsule.get("capabilities") or [], add_capabilities)
        if add_tags:
            capsule["tags"] = _dedupe_append(capsule.get("tags") or [], add_tags)
            capsule["when_to_use"] = _dedupe_append(capsule.get("when_to_use") or [], add_tags)

        _dump_yaml(capsule_path, capsule)
        _refresh_markdown_entrypoints(root, capsule)
        if lesson is not None:
            _upsert_lesson(root, lesson)

        report = validate_capsule_dir(root, warnings_ok=True)
        if not report["ok"]:
            raise SystemExit("updated capsule failed validation: " + "; ".join(report["errors"]))
        if dry_run:
            _restore_package(root, snapshot)
        return {
            "ok": True,
            "capsule_dir": str(root),
            "dry_run": dry_run,
            "conflicts": conflicts,
            "resolved_conflicts": resolved_conflicts,
        }
    except BaseException:
        _restore_package(root, snapshot)
        raise
    finally:
        snapshot.cleanup()


def _split_csv(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for raw in values or []:
        result.extend(item.strip() for item in str(raw).split(",") if item.strip())
    return result


def _lesson_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.lesson_id and not args.lesson_rule and not args.lesson_scope:
        return None
    return {
        "id": args.lesson_id,
        "scope": args.lesson_scope,
        "content_scope": args.lesson_content_scope,
        "rule": args.lesson_rule,
        "applies_when": _split_csv(args.applies_when),
        "promote_to": _split_csv(args.promote_to),
        "avoid": _split_csv(args.avoid),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely update a Video OKF capsule package.")
    parser.add_argument("capsule_dir")
    parser.add_argument("--display-name")
    parser.add_argument("--summary")
    parser.add_argument("--category")
    parser.add_argument("--status")
    parser.add_argument("--primary-workflow")
    parser.add_argument("--add-capability", action="append", default=[])
    parser.add_argument("--add-tag", action="append", default=[])
    parser.add_argument("--lesson-id")
    parser.add_argument("--lesson-scope")
    parser.add_argument("--lesson-content-scope", default="series")
    parser.add_argument("--lesson-rule")
    parser.add_argument("--applies-when", action="append", default=[])
    parser.add_argument("--promote-to", action="append", default=[])
    parser.add_argument("--avoid", action="append", default=[])
    parser.add_argument("--conflict-resolution")
    parser.add_argument("--conflict-report-json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = update_capsule_package(
            args.capsule_dir,
            display_name=args.display_name,
            summary=args.summary,
            category=args.category,
            status=args.status,
            primary_workflow=args.primary_workflow,
            add_capabilities=_split_csv(args.add_capability),
            add_tags=_split_csv(args.add_tag),
            lesson=_lesson_from_args(args),
            conflict_resolution=args.conflict_resolution,
            dry_run=args.dry_run,
        )
    except CapsuleUpdateConflictError as exc:
        if args.conflict_report_json:
            print(json.dumps({"ok": False, "conflicts": exc.conflicts}, ensure_ascii=False, indent=2))
        raise SystemExit(str(exc)) from exc
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        suffix = " (dry run)" if result["dry_run"] else ""
        print(f"updated capsule package: {result['capsule_dir']}{suffix}")


if __name__ == "__main__":
    main()
