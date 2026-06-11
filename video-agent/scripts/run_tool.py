#!/usr/bin/env python3
"""单工具调用封装脚本 — 消除 boilerplate，AI 只需传工具名和参数。

用法：
    python video-agent/scripts/run_tool.py \
    --tool "Gemini3ProImageGeneratorTool" \
    --params '{"prompt":"A cat cooking","output_path":"/tmp/cat.png","aspect_ratio":"9:16"}'
"""

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
import yaml

# ── boilerplate ──────────────────────────────────────────
# Skill 目录结构: video-agent/scripts/this_script.py → video-agent/lib/ 是工具库
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"

# project_root 指向 lib/ 目录（包含 custom_tools/, agents/, agno_agents/）
project_root = _LIB_DIR
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

load_video_agent_env(_SKILL_DIR)
# ─────────────────────────────────────────────────────────

def load_tool_registry() -> dict:
    registry_path = _LIB_DIR / "config" / "tool_registry.yaml"
    with registry_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    tools = data.get("tools") or {}
    return {
        name: config.get("module")
        for name, config in tools.items()
        if isinstance(config, dict) and config.get("module")
    }


def main():
    parser = argparse.ArgumentParser(description="单工具调用")
    parser.add_argument("--tool", required=True, help="工具类名，如 Gemini3ProImageGeneratorTool")
    parser.add_argument("--params", required=True, help="JSON 格式的参数")
    args = parser.parse_args()

    tool_name = args.tool
    params = json.loads(args.params)
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
