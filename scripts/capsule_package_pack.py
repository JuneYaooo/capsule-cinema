#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from capsule_package_validate import VIDEO_OKF_PROFILE, check_shareable_text, validate_capsule_dir


SHARE_PACKAGE_FORMAT = "video.okf.capsule.share.v1"
TEXT_SUFFIXES = {
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".py",
    ".txt",
    ".srt",
    ".ass",
    ".csv",
}
BLOCKED_PARTS = {"__pycache__", "output"}
BLOCKED_NAMES = {".DS_Store"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"expected YAML object: {path}")
    return data


def validate_share_package_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("invalid share package path: empty path")
    if "\\" in value:
        raise SystemExit(f"invalid share package path: backslash is not allowed: {value}")
    if "//" in value or value.endswith("/"):
        raise SystemExit(f"invalid share package path: empty segment is not allowed: {value}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise SystemExit(f"invalid share package path: absolute path is not allowed: {value}")
    if any(part in ("", ".", "..") for part in path.parts):
        raise SystemExit(f"invalid share package path: traversal is not allowed: {value}")
    return path.as_posix()


def _is_text_scannable(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"CARD.md", "capsule.yaml"}


def _reject_blocked_member(rel_path: Path) -> None:
    for part in rel_path.parts:
        if part in BLOCKED_PARTS:
            raise SystemExit(f"share package refused blocked runtime/cache file: {rel_path.as_posix()}")
        if part in BLOCKED_NAMES or part.startswith("."):
            raise SystemExit(f"share package refused hidden/transient file: {rel_path.as_posix()}")


def _scan_text_file(path: Path, label: str) -> None:
    if not _is_text_scannable(path):
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"share package refused non-UTF-8 text file: {label}") from exc
    errors = check_shareable_text(
        label,
        text,
        allow_artifact_manifest="scripts/" in label or label.endswith("quality/rules.yaml"),
    )
    if errors:
        raise SystemExit("share package refused unsafe text:\n" + "\n".join(f"- {item}" for item in errors[:10]))


def _target_path(output: str | Path, capsule_name: str) -> Path:
    out = Path(output).expanduser()
    if out.suffix == ".zip":
        return out.resolve()
    return (out / f"{capsule_name}.video-capsule.zip").resolve()


def _collect_files(root: Path, archive_root: str) -> list[tuple[Path, str, bytes]]:
    files: list[tuple[Path, str, bytes]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise SystemExit(f"share package refused symlink: {path.relative_to(root).as_posix()}")
        rel = path.relative_to(root)
        _reject_blocked_member(rel)
        archive_path = validate_share_package_path(f"{archive_root}/{rel.as_posix()}")
        _scan_text_file(path, archive_path)
        files.append((path, archive_path, path.read_bytes()))
    return files


def pack_capsule_package(
    capsule_dir: str | Path,
    *,
    output: str | Path = "dist/capsules",
    overwrite: bool = False,
) -> Path:
    root = Path(capsule_dir).expanduser().resolve()
    report = validate_capsule_dir(root, warnings_ok=True)
    if not report["ok"]:
        raise SystemExit("capsule validation failed before packaging: " + "; ".join(report["errors"]))

    capsule = _read_yaml(root / "capsule.yaml")
    name = str(capsule.get("name") or "").strip()
    if not name:
        raise SystemExit("capsule.yaml name is required")
    archive_root = validate_share_package_path(f"{name}.capsule")
    target = _target_path(output, name)
    if target.exists() and not overwrite:
        raise SystemExit(f"share package already exists: {target}")
    if target.is_relative_to(root):
        raise SystemExit(f"share package output cannot be inside capsule directory: {target}")

    files = _collect_files(root, archive_root)
    manifest_files = [
        {
            "path": archive_path,
            "sha256": _sha256_bytes(data),
            "size": len(data),
        }
        for _, archive_path, data in files
    ]
    manifest = {
        "package_format": SHARE_PACKAGE_FORMAT,
        "profile": VIDEO_OKF_PROFILE,
        "name": name,
        "display_name": capsule.get("display_name") or name,
        "version": capsule.get("version"),
        "status": capsule.get("status"),
        "category": capsule.get("category") or "",
        "primary_workflow": capsule.get("primary_workflow") or "",
        "summary": capsule.get("summary") or "",
        "capabilities": capsule.get("capabilities") or [],
        "tags": capsule.get("tags") or [],
        "capsule_dir": archive_root,
        "exported_at": _now(),
        "files": manifest_files,
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for _, archive_path, data in files:
            archive.writestr(archive_path, data)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack a Video OKF capsule directory into a shareable zip.")
    parser.add_argument("capsule_dir")
    parser.add_argument("--out", default="dist/capsules")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package = pack_capsule_package(args.capsule_dir, output=args.out, overwrite=args.overwrite)
    payload = {"ok": True, "package": str(package)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"packed capsule package: {package}")


if __name__ == "__main__":
    main()
