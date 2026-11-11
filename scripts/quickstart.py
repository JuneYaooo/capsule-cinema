#!/usr/bin/env python3
"""First-run check: what works on this machine now, and the cheapest next step.

Reads only whether an environment variable is set. Never prints a value.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
LIB_DIR = ROOT / "lib"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

MODALITIES = ["image", "video", "voice", "lip_sync", "action_transfer"]
PLANNING_ENV = ["CREW_API_KEY", "CREW_BASE_URL", "CREW_MODEL_NAME"]
CORE_MODULES = [("yaml", "PyYAML"), ("PIL", "pillow"), ("numpy", "numpy"), ("dotenv", "python-dotenv")]
COST_ORDER = {"free": 0, "low": 1, "medium": 2, "high": 3}
REPO_URL = "https://github.com/JuneYaooo/capsule-cinema"
BROWSER_BINARIES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "chrome", "msedge"]
BROWSER_PATHS = [
    "/Applications/Google Chrome.app",
    "/Applications/Chromium.app",
    "/Applications/Microsoft Edge.app",
    "~/Library/Caches/ms-playwright",
    "~/.cache/ms-playwright",
    "~/AppData/Local/ms-playwright",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]

TEXT: dict[str, dict[str, Any]] = {
    "zh": {
        "title": "Capsule Cinema 上手自检",
        "sep": "：",
        "join": "、",
        "modality": {"image": "图片生成", "video": "视频生成", "voice": "配音", "lip_sync": "对口型", "action_transfer": "动作迁移"},
        "h_runtime": "【运行环境】",
        "py_old": "（需要 3.12 或更高）",
        "deps_missing": "缺少依赖：{}",
        "deps_fix": "运行：python3.12 -m pip install -r lib/requirements.txt",
        "deps_ok": "Python 依赖",
        "ffmpeg_missing": "（渲染、配字幕和合成成片前必须安装）",
        "capsules": "可用配方 {} 个",
        "browser_ok": "浏览器（项目介绍视频要用它截网页）",
        "browser_unknown": "未检测到 Chrome / Edge / Playwright 浏览器。项目介绍视频需要截网页：",
        "browser_fix": "Agent 自带浏览器工具时可忽略；否则运行 npx playwright install chromium",
        "env_file": "密钥文件：{}",
        "env_none": "未找到 .env（也可以用系统环境变量或 Agent 的密钥配置）",
        "planner_on": "分镜规划模型：已配置 CREW_*",
        "planner_off": "分镜规划模型：未配置 CREW_*，分镜由当前 Agent 在对话中完成",
        "h_channels": "【生成渠道】只检查变量是否已设置，不读取内容",
        "not_configured": "未配置",
        "voice_fallback": "未配置云端音色，会用本机语音兜底（能出声，音质一般）",
        "unlock": "配置 {env} 可启用 {provider}",
        "tier": "，费用档 {}",
        "h_paths": "【现在可以做什么】",
        "missing": "——还缺：{}",
        "h_next": "【建议的下一步】",
        "next_fix": "先补齐上面「运行环境」里打 ✗ 的项目，再重新运行本脚本。",
        "next_go": "把「{}」下面那段话发给 Agent，先跑通一条。",
        "next_agnes": "想试 AI 画面：AGNES_API_KEY 有免费层，适合第一次试一张图和几秒样片。",
        "next_keys": "密钥写进根目录 .env（参考 lib/.env.example）或系统环境变量，不要粘贴到对话里。",
        "need_runtime": "运行环境",
        "need_ffmpeg": "FFmpeg",
        "need_capsule": "内置配方 repo_signal_grid",
        "need_visual": "一条图片或视频渠道",
        "need_image": "图片渠道",
        "need_video": "视频渠道",
        "paths": {
            "repo_showcase": (
                "项目介绍视频（不需要任何生成密钥）",
                f"使用内置视频配方 `repo_signal_grid`，为这个项目制作一条项目介绍视频：\n{REPO_URL}",
            ),
            "storyboard": (
                "只出分镜（不计费）",
                "用 Capsule Cinema 为「一只橘猫深夜经营路边摊」做一个 25 秒竖屏分镜。\n先不要生成图片、视频和配音，也不要调用任何计费 API。",
            ),
            "sample_shot": ("试做一个代表镜头", "分镜确认了，只试做一个代表镜头给我看，先不要批量生成。"),
            "full_video": (
                "完整 AI 短视频",
                "帮我用 Capsule Cinema 做一条 25 秒竖屏视频：一只橘猫深夜经营路边摊，温暖治愈一点。\n先给我看分镜，确认后只试做一个代表镜头。",
            ),
        },
    },
    "en": {
        "title": "Capsule Cinema first-run check",
        "sep": ": ",
        "join": ", ",
        "modality": {"image": "Image generation", "video": "Video generation", "voice": "Voice", "lip_sync": "Lip sync", "action_transfer": "Action transfer"},
        "h_runtime": "[Runtime]",
        "py_old": " (3.12 or newer is required)",
        "deps_missing": "Missing packages: {}",
        "deps_fix": "Run: python3.12 -m pip install -r lib/requirements.txt",
        "deps_ok": "Python packages",
        "ffmpeg_missing": " (required before rendering, subtitles, or final assembly)",
        "capsules": "{} recipes available",
        "browser_ok": "Browser (the project showcase captures web pages with it)",
        "browser_unknown": "No Chrome / Edge / Playwright browser detected. The project showcase captures web pages:",
        "browser_fix": "Ignore this if your agent has its own browser tool; otherwise run npx playwright install chromium",
        "env_file": "Credentials file: {}",
        "env_none": "no .env found (system environment variables or agent-managed secrets also work)",
        "planner_on": "Storyboard planner: CREW_* configured",
        "planner_off": "Storyboard planner: CREW_* not set, so the current agent drafts storyboards in the conversation",
        "h_channels": "[Providers] Checks only whether a variable is set, never its value",
        "not_configured": "not configured",
        "voice_fallback": "no cloud voice configured; the local system voice is used as a fallback (works, modest quality)",
        "unlock": "Set {env} to enable {provider}",
        "tier": ", cost tier {}",
        "h_paths": "[What you can make now]",
        "missing": " - still needs: {}",
        "h_next": "[Suggested next step]",
        "next_fix": "Fix the items marked ✗ under Runtime, then run this check again.",
        "next_go": "Send the prompt under \"{}\" to your agent and finish one video first.",
        "next_agnes": "To try AI footage: AGNES_API_KEY has a free tier, enough for a first image and a few seconds of sample video.",
        "next_keys": "Put credentials in a root .env (see lib/.env.example) or system environment variables. Never paste them into chat.",
        "need_runtime": "runtime",
        "need_ffmpeg": "FFmpeg",
        "need_capsule": "the included repo_signal_grid recipe",
        "need_visual": "an image or video provider",
        "need_image": "an image provider",
        "need_video": "a video provider",
        "paths": {
            "repo_showcase": (
                "Project showcase video (no generation keys needed)",
                f"Use the included `repo_signal_grid` video recipe to make a project-introduction video for:\n{REPO_URL}",
            ),
            "storyboard": (
                "Storyboard only (no cost)",
                "Use Capsule Cinema to storyboard a 25-second vertical video about an orange cat running a late-night street-food stand.\nDo not generate images, video, or voice yet, and do not call any paid API.",
            ),
            "sample_shot": (
                "One representative scene",
                "The storyboard is approved. Make only one representative scene for me to review. Do not batch-generate yet.",
            ),
            "full_video": (
                "Complete AI short video",
                "Use Capsule Cinema to make a warm 25-second vertical video about an orange cat running a late-night street-food stand.\nShow me the storyboard first. After I approve it, make only one representative scene.",
            ),
        },
    },
}


def _is_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _load_entries() -> tuple[list[dict[str, Any]], str | None]:
    """Registered tools plus catalog voices, as one list of provider entries."""
    try:
        from src.config_registry import load_registry, load_tool_capabilities
    except ModuleNotFoundError as exc:
        return [], f"missing Python package {exc.name}"
    try:
        tools = load_tool_capabilities()
        voices = load_registry("voice_catalog.yaml", "voices")
    except Exception as exc:  # noqa: BLE001 - report a broken registry instead of crashing
        return [], f"cannot read provider registry: {exc}"
    entries = [dict(config, name=name) for name, config in sorted(tools.items()) if isinstance(config, dict)]
    if voices:
        # The voice catalog is the source of truth for narration; it covers every TTS provider.
        entries = [entry for entry in entries if entry.get("modality") != "voice"]
        entries += [dict(config, name=name) for name, config in sorted(voices.items()) if isinstance(config, dict)]
    return entries, None


def _missing_modules() -> list[str]:
    missing = []
    for module, package in CORE_MODULES:
        try:
            __import__(module)
        except ModuleNotFoundError:
            missing.append(package)
    return missing


def _browser_detected() -> bool:
    if any(shutil.which(name) for name in BROWSER_BINARIES):
        return True
    return any(Path(item).expanduser().exists() for item in BROWSER_PATHS)


def build_report() -> dict[str, Any]:
    env_path = load_video_agent_env(ROOT)
    entries, registry_error = _load_entries()

    channels: dict[str, dict[str, Any]] = {}
    for modality in MODALITIES:
        ready: list[str] = []
        fallback: list[str] = []
        unlock: list[dict[str, Any]] = []
        for config in entries:
            if config.get("modality") != modality:
                continue
            required = [str(item) for item in config.get("requires_env") or []]
            missing = [item for item in required if not _is_set(item)]
            provider = str(config.get("provider") or config["name"])
            if not required:
                target = fallback
            elif not missing:
                target = ready
            else:
                unlock.append({"provider": provider, "missing_env": missing, "cost_tier": str(config.get("cost_tier") or "")})
                continue
            if provider not in target:
                target.append(provider)
        # Cheapest, fewest-variables option first; one row per provider.
        unlock.sort(key=lambda item: (COST_ORDER.get(item["cost_tier"], 9), len(item["missing_env"])))
        seen: set[str] = set(ready)
        unlock = [item for item in unlock if not (item["provider"] in seen or seen.add(item["provider"]))]
        channels[modality] = {"ready": ready, "fallback": fallback, "unlock": unlock}

    missing_modules = _missing_modules()
    python_ok = sys.version_info >= (3, 12)
    ffmpeg_ok = bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))
    capsule_count = len(list((ROOT / "capsules").glob("*.capsule")))
    runtime_ok = python_ok and not missing_modules and registry_error is None and capsule_count > 0
    showcase_capsule = (ROOT / "capsules" / "repo_signal_grid.capsule").is_dir()

    image_ok = bool(channels["image"]["ready"])
    video_ok = bool(channels["video"]["ready"])

    def needs(*pairs: tuple[str, bool]) -> list[str]:
        return [key for key, bad in pairs if bad]

    # Narration never blocks a video: without a cloud voice the runtime falls back to the local system voice.
    paths = [
        {"key": "repo_showcase", "needs": needs(("need_runtime", not runtime_ok), ("need_ffmpeg", not ffmpeg_ok), ("need_capsule", not showcase_capsule))},
        {"key": "storyboard", "needs": needs(("need_runtime", not runtime_ok))},
        {"key": "sample_shot", "needs": needs(("need_runtime", not runtime_ok), ("need_visual", not (image_ok or video_ok)))},
        {
            "key": "full_video",
            "needs": needs(
                ("need_image", not image_ok),
                ("need_video", not video_ok),
                ("need_ffmpeg", not ffmpeg_ok),
                ("need_runtime", not runtime_ok),
            ),
        },
    ]
    for item in paths:
        item["ready"] = not item["needs"]

    return {
        "schema": "capsule_cinema.quickstart.v1",
        "root": str(ROOT),
        "runtime": {
            "python": ".".join(map(str, sys.version_info[:3])),
            "python_ok": python_ok,
            "missing_python_packages": missing_modules,
            "ffmpeg_ok": ffmpeg_ok,
            "browser_detected": _browser_detected(),
            "registry_error": registry_error,
            "capsule_count": capsule_count,
            "env_file": str(env_path) if env_path else None,
            "planning_model_configured": all(_is_set(name) for name in PLANNING_ENV),
        },
        "channels": channels,
        "paths": paths,
    }


def localize(report: dict[str, Any], lang: str) -> dict[str, Any]:
    """Attach human-readable titles, prompts, and need labels in the chosen language."""
    text = TEXT[lang]
    for modality, channel in report["channels"].items():
        channel["label"] = text["modality"][modality]
    for item in report["paths"]:
        item["title"], item["prompt"] = text["paths"][item["key"]]
        item["needs"] = [text[key] for key in item["needs"]]
    return report


def render_text(report: dict[str, Any], lang: str) -> str:
    text = TEXT[lang]
    runtime = report["runtime"]
    sep = text["sep"]
    mark = lambda ok: "✓" if ok else "✗"  # noqa: E731
    lines = [text["title"], "", text["h_runtime"]]

    lines.append(f"  {mark(runtime['python_ok'])} Python {runtime['python']}" + ("" if runtime["python_ok"] else text["py_old"]))
    if runtime["missing_python_packages"]:
        lines.append("  ✗ " + text["deps_missing"].format(", ".join(runtime["missing_python_packages"])))
        lines.append("    " + text["deps_fix"])
    else:
        lines.append("  ✓ " + text["deps_ok"])
    lines.append(f"  {mark(runtime['ffmpeg_ok'])} FFmpeg / FFprobe" + ("" if runtime["ffmpeg_ok"] else text["ffmpeg_missing"]))
    if runtime["registry_error"]:
        lines.append(f"  ✗ {runtime['registry_error']}")
    lines.append(f"  {mark(runtime['capsule_count'] > 0)} " + text["capsules"].format(runtime["capsule_count"]))
    if runtime["browser_detected"]:
        lines.append("  ✓ " + text["browser_ok"])
    else:
        lines.append("  ? " + text["browser_unknown"])
        lines.append("    " + text["browser_fix"])
    lines.append("  · " + text["env_file"].format(runtime["env_file"] or text["env_none"]))
    lines.append("  · " + (text["planner_on"] if runtime["planning_model_configured"] else text["planner_off"]))

    lines += ["", text["h_channels"]]
    for modality, channel in report["channels"].items():
        if channel["ready"]:
            lines.append(f"  ✓ {channel['label']}{sep}{', '.join(channel['ready'])}")
            continue
        if modality == "voice" and channel["fallback"]:
            lines.append(f"  △ {channel['label']}{sep}{text['voice_fallback']}")
        else:
            lines.append(f"  ✗ {channel['label']}{sep}{text['not_configured']}")
        for option in channel["unlock"][:3]:
            tier = text["tier"].format(option["cost_tier"]) if option["cost_tier"] else ""
            lines.append("      " + text["unlock"].format(env=" + ".join(option["missing_env"]), provider=option["provider"]) + tier)

    lines += ["", text["h_paths"]]
    for item in report["paths"]:
        if item["ready"]:
            lines.append(f"  ✓ {item['title']}")
            lines.extend(f"      {row}" for row in item["prompt"].splitlines())
        else:
            lines.append(f"  ✗ {item['title']}" + text["missing"].format(text["join"].join(item["needs"])))

    lines += ["", text["h_next"]]
    first_ready = next((item for item in report["paths"] if item["ready"]), None)
    lines.append("  " + (text["next_go"].format(first_ready["title"]) if first_ready else text["next_fix"]))
    channels = report["channels"]
    if not channels["image"]["ready"] and not channels["video"]["ready"]:
        lines.append("  " + text["next_agnes"])
    lines.append("  " + text["next_keys"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lang", choices=sorted(TEXT), default="zh", help="Output language (default: zh)")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()
    report = localize(build_report(), args.lang)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_text(report, args.lang))


if __name__ == "__main__":
    main()
