#!/usr/bin/env python3
"""Print a compact provider menu from the Capsule Cinema tool registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "lib"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402


load_video_agent_env(SKILL_DIR)


REGISTRY_PATH = LIB_DIR / "config" / "tool_registry.yaml"


def _load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_provider_menu(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Build a human-sized capability menu from ``tool_registry.yaml``."""
    registry = _load_registry(path)
    tools = registry.get("tools") or {}
    grouped: dict[str, list[dict[str, Any]]] = {}

    for name, config in sorted(tools.items()):
        if not isinstance(config, dict):
            continue
        category = str(config.get("category") or "uncategorized")
        grouped.setdefault(category, []).append(
            {
                "name": name,
                "provider": config.get("provider") or "",
                "module": config.get("module") or "",
                "limits": config.get("limits") or {},
                "strengths": config.get("strengths") or [],
            }
        )

    capabilities = [
        {
            "category": category,
            "total": len(items),
            "providers": sorted({item["provider"] for item in items if item["provider"]}),
            "tools": items,
        }
        for category, items in sorted(grouped.items())
    ]

    return {
        "schema": "capsule_cinema.provider_menu.v1",
        "registry_path": str(path),
        "capabilities": capabilities,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    menu = build_provider_menu()
    print(json.dumps(menu, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
