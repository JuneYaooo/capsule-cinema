import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

for path in (ROOT / "lib", ROOT / "scripts"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from capsule_runtime import load_capsule_package  # noqa: E402


def active_capsule_dir(name: str) -> Path:
    return ROOT / "capsules" / f"{name}.capsule"


def load_active_capsule(name: str) -> dict:
    capsule = load_capsule_package(name)
    if capsule is None:
        raise AssertionError(f"missing active capsule package: {active_capsule_dir(name)}")
    return capsule


def package_files(name: str) -> set[str]:
    capsule_dir = active_capsule_dir(name)
    return {
        path.relative_to(capsule_dir).as_posix()
        for path in capsule_dir.rglob("*")
        if path.is_file()
    }


def package_relative_path(name: str, path: str | Path) -> str:
    capsule_dir = active_capsule_dir(name).resolve()
    return Path(path).resolve().relative_to(capsule_dir).as_posix()


def read_package_text(name: str, rel_path: str) -> str:
    return (active_capsule_dir(name) / rel_path).read_text(encoding="utf-8")


def package_file_entries(name: str) -> list[dict]:
    capsule_dir = active_capsule_dir(name)
    entries = []
    for path in sorted(item for item in capsule_dir.rglob("*") if item.is_file()):
        data = path.read_bytes()
        entries.append(
            {
                "package_path": path.relative_to(capsule_dir).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    return entries


def recipe_text(capsule: dict) -> str:
    method = capsule.get("method") or {}
    return "\n".join(str(value) for value in method.values())
