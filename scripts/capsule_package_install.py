#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import yaml

from capsule_package_pack import SHARE_PACKAGE_FORMAT, validate_share_package_path
from capsule_package_validate import VIDEO_OKF_PROFILE, validate_capsule_dir


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SystemExit(f"invalid video capsule share package manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise SystemExit("invalid video capsule share package manifest: must be an object")
    return manifest


def _verify_manifest(manifest: dict[str, Any]) -> str:
    if manifest.get("package_format") != SHARE_PACKAGE_FORMAT:
        raise SystemExit(
            f"unsupported video capsule share package format: {manifest.get('package_format')}"
        )
    if manifest.get("profile") != VIDEO_OKF_PROFILE:
        raise SystemExit(f"unsupported video capsule profile: {manifest.get('profile')}")
    capsule_dir = validate_share_package_path(manifest.get("capsule_dir"))
    if "/" in capsule_dir or not capsule_dir.endswith(".capsule"):
        raise SystemExit(f"invalid capsule_dir in share manifest: {capsule_dir}")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise SystemExit("invalid video capsule share package manifest: files must be a non-empty list")
    return capsule_dir


def _write_verified_files(archive: zipfile.ZipFile, manifest: dict[str, Any], staging_root: Path) -> None:
    capsule_dir = _verify_manifest(manifest)
    declared_paths: set[str] = set()
    member_names = [info.filename for info in archive.infolist() if not info.is_dir()]
    if len(member_names) != len(set(member_names)):
        raise SystemExit("share package contains duplicate file entries")
    names = set(member_names)
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise SystemExit("invalid video capsule share package manifest: file entry must be an object")
        package_path = validate_share_package_path(entry.get("path"))
        if not package_path.startswith(f"{capsule_dir}/"):
            raise SystemExit(f"share package file escapes capsule root: {package_path}")
        if package_path not in names:
            raise SystemExit(f"share package corrupt: missing file {package_path}")
        data = archive.read(package_path)
        if _sha256_bytes(data) != entry.get("sha256"):
            raise SystemExit(f"share package checksum mismatch: {package_path}")
        if len(data) != int(entry.get("size", -1)):
            raise SystemExit(f"share package size mismatch: {package_path}")
        declared_paths.add(package_path)
        dest = (staging_root / package_path).resolve()
        if not dest.is_relative_to(staging_root.resolve()):
            raise SystemExit(f"share package file escapes staging root: {package_path}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    unexpected = sorted(names - declared_paths - {"manifest.json"})
    if unexpected:
        raise SystemExit(f"share package contains undeclared file: {unexpected[0]}")


def _validate_manifest_matches_capsule(manifest: dict[str, Any], capsule_dir: Path) -> None:
    capsule = yaml.safe_load((capsule_dir / "capsule.yaml").read_text(encoding="utf-8")) or {}
    if not isinstance(capsule, dict):
        raise SystemExit("installed capsule.yaml must be an object")
    for key in ("name", "profile", "primary_workflow"):
        if capsule.get(key) != manifest.get(key):
            raise SystemExit(f"share manifest {key} does not match capsule.yaml")
    if capsule.get("tags") != manifest.get("tags"):
        raise SystemExit("share manifest tags do not match capsule.yaml")
    if capsule.get("capabilities") != manifest.get("capabilities"):
        raise SystemExit("share manifest capabilities do not match capsule.yaml")


def install_capsule_package(
    package: str | Path,
    *,
    output_root: str | Path = "capsules",
    force: bool = False,
) -> Path:
    package_path = Path(package).expanduser().resolve()
    if not package_path.is_file():
        raise SystemExit(f"video capsule share package not found: {package_path}")
    out_root = Path(output_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        staging_root = Path(tmp).resolve()
        with zipfile.ZipFile(package_path) as archive:
            manifest = _read_manifest(archive)
            capsule_dir_name = _verify_manifest(manifest)
            _write_verified_files(archive, manifest, staging_root)

        staged_capsule = staging_root / capsule_dir_name
        _validate_manifest_matches_capsule(manifest, staged_capsule)
        report = validate_capsule_dir(staged_capsule, warnings_ok=True)
        if not report["ok"]:
            raise SystemExit("installed capsule failed validation: " + "; ".join(report["errors"]))

        target = (out_root / capsule_dir_name).resolve()
        if target.parent != out_root:
            raise SystemExit(f"install target escapes output root: {target}")
        if target.exists() and not force:
            raise SystemExit(f"capsule package already exists: {target} (use --force to overwrite)")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(staged_capsule, target)
        return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a Video OKF capsule share package.")
    parser.add_argument("package")
    parser.add_argument("--out", default="capsules")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    installed = install_capsule_package(args.package, output_root=args.out, force=args.force)
    payload = {"ok": True, "capsule_dir": str(installed)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"installed capsule package: {installed}")


if __name__ == "__main__":
    main()
