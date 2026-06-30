#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
        "rule": str(lesson["rule"]).strip(),
    }
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
        return {"ok": True, "capsule_dir": str(root), "dry_run": dry_run}
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
    parser.add_argument("--lesson-rule")
    parser.add_argument("--applies-when", action="append", default=[])
    parser.add_argument("--promote-to", action="append", default=[])
    parser.add_argument("--avoid", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

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
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        suffix = " (dry run)" if result["dry_run"] else ""
        print(f"updated capsule package: {result['capsule_dir']}{suffix}")


if __name__ == "__main__":
    main()
