#!/usr/bin/env python3
"""Seed the local SQLite capsule store from lib/config/initial_capsules.json."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "lib" / "config" / "initial_capsules.json"
CAPSULE_STORE = ROOT / "scripts" / "capsule_store.py"


def json_arg(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def optional_arg(cmd: list[str], flag: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, (dict, list)):
        if not value:
            return
        cmd.extend([flag, json_arg(value)])
        return
    text = str(value)
    if text:
        cmd.extend([flag, text])


def upsert_capsule(capsule: dict, env: dict[str, str]) -> None:
    tags = capsule.get("tags", "")
    if isinstance(tags, list):
        tags = ",".join(str(item) for item in tags)

    cmd = [
        sys.executable,
        str(CAPSULE_STORE),
        "upsert",
        "--name",
        capsule["name"],
    ]
    optional_arg(cmd, "--display-name", capsule.get("display_name"))
    optional_arg(cmd, "--status", capsule.get("status", "draft"))
    optional_arg(cmd, "--execution-mode", capsule.get("execution_mode", "preset"))
    optional_arg(cmd, "--description", capsule.get("description"))
    optional_arg(cmd, "--category", capsule.get("category"))
    optional_arg(cmd, "--tags", tags)
    optional_arg(cmd, "--config-json", capsule.get("config"))
    optional_arg(cmd, "--method-json", capsule.get("method"))
    optional_arg(cmd, "--input-schema-json", capsule.get("input_schema"))
    optional_arg(cmd, "--quality-rules-json", capsule.get("quality_rules"))
    optional_arg(cmd, "--local-assets-json", capsule.get("local_assets"))
    optional_arg(cmd, "--notes", capsule.get("notes"))

    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-json", default=str(DEFAULT_SEED), help="Seed JSON file")
    parser.add_argument("--db", help="SQLite DB path. Sets VIDEO_CAPSULE_DB for this run.")
    parser.add_argument("--list", action="store_true", help="List capsules after seeding")
    args = parser.parse_args()

    seed_path = Path(args.seed_json).expanduser().resolve()
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    capsules = data.get("capsules") or []
    if not capsules:
        raise SystemExit(f"No capsules found in {seed_path}")

    env = os.environ.copy()
    if args.db:
        env["VIDEO_CAPSULE_DB"] = str(Path(args.db).expanduser().resolve())

    subprocess.run([sys.executable, str(CAPSULE_STORE), "init"], cwd=ROOT, env=env, check=True)
    for capsule in capsules:
        upsert_capsule(capsule, env)
        print(f"seeded capsule: {capsule['name']}")

    if args.list:
        subprocess.run([sys.executable, str(CAPSULE_STORE), "list"], cwd=ROOT, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
