#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL_DIR = ROOT / "skills" / "capsule-cinema"


def fail(message: str) -> None:
    raise SystemExit(f"invalid skill distribution: {message}")


def read_frontmatter(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail("SKILL.md must start with YAML frontmatter")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError:
        fail("SKILL.md frontmatter is not closed")
    if not body.strip():
        fail("SKILL.md body is empty")

    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = re.fullmatch(r"([a-z][a-z0-9-]*):\s*(.+)", line)
        if not match:
            fail(f"unsupported or malformed frontmatter line: {line!r}")
        values[match.group(1)] = match.group(2).strip().strip('"\'')
    return values


def main() -> None:
    if any(path.name == "skill.md" for path in ROOT.iterdir()):
        fail("legacy lowercase skill.md is not supported")

    root_skill = ROOT / "SKILL.md"
    source_skill = SOURCE_SKILL_DIR / "SKILL.md"
    if source_skill.is_file():
        if root_skill.exists():
            fail("a root SKILL.md must not shadow the standard skills/ directory")
        skill_dir = SOURCE_SKILL_DIR
        bootstrap = skill_dir / "scripts" / "bootstrap-runtime.sh"
        if not bootstrap.is_file() or not bootstrap.stat().st_mode & 0o111:
            fail("bootstrap-runtime.sh is missing or not executable")

        manifest = json.loads((ROOT / "openclaw.plugin.json").read_text(encoding="utf-8"))
        if "skills/capsule-cinema" not in manifest.get("skills", []):
            fail("openclaw.plugin.json does not expose the standard skill directory")
    elif root_skill.is_file():
        skill_dir = ROOT
    else:
        fail("no standard SKILL.md entry was found")

    frontmatter = read_frontmatter(skill_dir / "SKILL.md")
    if set(frontmatter) != {"name", "description"}:
        fail("SKILL.md frontmatter must contain only name and description")
    if frontmatter["name"] != skill_dir.name:
        fail("skill name must match its parent directory")
    if not 1 <= len(frontmatter["description"]) <= 1024:
        fail("skill description must contain 1 to 1024 characters")

    print("Skill distribution is valid.")


if __name__ == "__main__":
    main()
