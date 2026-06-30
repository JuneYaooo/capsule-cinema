from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class CapsulePackageError(Exception):
    """Raised when a capsule package cannot be resolved or loaded."""


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEARCH_ROOTS = [ROOT / "capsules"]


def _read_yaml(path: Path, fallback: Any) -> Any:
    if not path.exists():
        raise CapsulePackageError(f"missing YAML file: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or fallback
    except yaml.YAMLError as exc:
        raise CapsulePackageError(f"invalid YAML file: {path}: {exc}") from exc


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CapsulePackageError(f"missing text file: {path}")
    return path.read_text(encoding="utf-8")


def resolve_capsule_dir(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> Path:
    value = Path(name_or_path).expanduser()
    if value.exists():
        candidate = value.resolve()
        if candidate.is_dir() and (candidate / "capsule.yaml").is_file():
            return candidate
        raise CapsulePackageError(f"not a capsule package directory: {candidate}")

    name = str(name_or_path).strip()
    if not name:
        raise CapsulePackageError("empty capsule name")
    candidates = [name]
    if not name.endswith(".capsule"):
        candidates.append(f"{name}.capsule")

    roots = [Path(item).expanduser() for item in (search_roots or DEFAULT_SEARCH_ROOTS)]
    for root in roots:
        for candidate_name in candidates:
            candidate = (root / candidate_name).resolve()
            if candidate.is_dir() and (candidate / "capsule.yaml").is_file():
                return candidate
    raise CapsulePackageError(f"capsule not found: {name}")


def _load_capsule_yaml(capsule_dir: Path) -> dict[str, Any]:
    data = _read_yaml(capsule_dir / "capsule.yaml", {})
    if not isinstance(data, dict):
        raise CapsulePackageError(f"capsule.yaml must be an object: {capsule_dir}")
    return data


def load_capsule_card(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> dict[str, Any]:
    capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    capsule = _load_capsule_yaml(capsule_dir)
    card_path = capsule_dir / "CARD.md"
    return {
        **capsule,
        "capsule_dir": str(capsule_dir),
        "card_path": str(card_path),
        "card_markdown": _read_text(card_path),
    }


def load_runtime_contract(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> dict[str, Any]:
    capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    runtime = _read_yaml(capsule_dir / "contracts" / "runtime.yaml", {})
    if not isinstance(runtime, dict):
        raise CapsulePackageError("contracts/runtime.yaml must be an object")
    return runtime


def _stage_files(capsule: dict[str, Any], stage: str) -> list[str]:
    read_order = capsule.get("read_order") if isinstance(capsule.get("read_order"), dict) else {}
    files = read_order.get(stage)
    if not isinstance(files, list):
        raise CapsulePackageError(f"stage not declared in read_order: {stage}")
    return [str(item) for item in files if str(item).strip()]


def load_stage_context(
    name_or_path: str | Path,
    stage: str,
    search_roots: list[str | Path] | None = None,
) -> dict[str, Any]:
    capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    capsule = _load_capsule_yaml(capsule_dir)
    files: dict[str, str] = {}
    for rel_path in _stage_files(capsule, stage):
        target = (capsule_dir / rel_path).resolve()
        if not target.is_relative_to(capsule_dir.resolve()):
            raise CapsulePackageError(f"read_order path escapes capsule: {rel_path}")
        files[rel_path] = _read_text(target)
    card_markdown = files.get("CARD.md") or files.get("./CARD.md") or ""
    return {
        "stage": stage,
        "capsule_dir": str(capsule_dir),
        "capsule": capsule,
        "card_markdown": card_markdown,
        "files": files,
    }


def load_quality_rules(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> list[dict[str, Any]]:
    capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    data = _read_yaml(capsule_dir / "quality" / "rules.yaml", {})
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        raise CapsulePackageError("quality/rules.yaml must contain a rules list")
    return [item for item in rules if isinstance(item, dict)]


def load_assets_index(
    name_or_path: str | Path,
    search_roots: list[str | Path] | None = None,
) -> list[dict[str, Any]]:
    capsule_dir = resolve_capsule_dir(name_or_path, search_roots=search_roots)
    data = _read_yaml(capsule_dir / "assets" / "index.yaml", {})
    assets = data.get("assets") if isinstance(data, dict) else None
    if not isinstance(assets, list):
        raise CapsulePackageError("assets/index.yaml must contain an assets list")
    return [item for item in assets if isinstance(item, dict)]
