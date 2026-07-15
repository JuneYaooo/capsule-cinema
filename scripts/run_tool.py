#!/usr/bin/env python3
"""单工具调用封装脚本 — 消除 boilerplate，AI 只需传工具名和参数。

Public tools come from ``lib/config/tool_registry.yaml``. Optional local-only
tools are merged from ``local-channels/tool_registry.yaml``.
"""

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

# ── boilerplate ──────────────────────────────────────────
# Skill 目录结构: scripts/this_script.py → lib/ 是工具库
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"

# project_root 指向 lib/ 目录（包含 custom_tools/, video_workflows/, src/）
project_root = _LIB_DIR
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402
from output_guard import normalize_output_params  # noqa: E402
from src.config_registry import load_tool_registry as load_registry_records  # noqa: E402

load_video_agent_env(_SKILL_DIR)
# ─────────────────────────────────────────────────────────

def load_tool_registry() -> dict:
    tools = load_registry_records()
    return {
        name: config.get("module")
        for name, config in tools.items()
        if isinstance(config, dict) and config.get("module")
    }


def main():
    parser = argparse.ArgumentParser(description="单工具调用")
    parser.add_argument("--tool", required=True, help="已注册的工具类名")
    parser.add_argument("--params", required=True, help="JSON 格式的参数")
    args = parser.parse_args()

    tool_name = args.tool
    try:
        params = normalize_output_params(json.loads(args.params))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"错误：{exc}")
        sys.exit(1)
    tool_registry = load_tool_registry()

    if tool_name not in tool_registry:
        print(f"错误：未知工具 {tool_name}")
        print(f"可用工具：{', '.join(sorted(tool_registry.keys()))}")
        sys.exit(1)

    module_path = tool_registry[tool_name]
    module = importlib.import_module(module_path)
    tool_class = getattr(module, tool_name)
    tool = tool_class()

    result = tool._run(**params)

    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
