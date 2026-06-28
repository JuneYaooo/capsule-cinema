#!/usr/bin/env python3
"""Print a compact provider menu from the Capsule Cinema capability registry."""

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


REGISTRY_PATH = LIB_DIR / "config" / "tool_capabilities.yaml"

CATEGORY_BY_MODALITY = {
    "image": "image_generation",
    "video": "video_generation",
    "voice": "audio_generation",
    "music": "music_generation",
    "lip_sync": "lip_sync",
    "action_transfer": "action_animation",
}


def _load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _category_for_tool(config: dict[str, Any]) -> str:
    modality = str(config.get("modality") or "").strip()
    return str(config.get("category") or CATEGORY_BY_MODALITY.get(modality) or modality or "uncategorized")


def build_provider_menu(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Build a human-sized capability menu from ``tool_capabilities.yaml``."""
    registry = _load_registry(path)
    tools = registry.get("tools") or {}
    grouped: dict[str, list[dict[str, Any]]] = {}

    for name, config in sorted(tools.items()):
        if not isinstance(config, dict):
            continue
        provides = config.get("provides") or {}
        category = _category_for_tool(config)
        grouped.setdefault(category, []).append(
            {
                "name": name,
                "modality": config.get("modality") or "",
                "provider": config.get("provider") or "",
                "module": config.get("module") or "",
                "provides": provides,
                "limits": provides.get("limits") or {},
                "strengths": config.get("strengths") or config.get("tags") or [],
                "requires_env": config.get("requires_env") or [],
                "cost_tier": config.get("cost_tier") or "",
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
