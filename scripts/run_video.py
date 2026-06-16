#!/usr/bin/env python3
"""完整视频生成封装脚本 — 消除 boilerplate，AI 只需传参数。

用法：
    python scripts/run_video.py \
    --user_requirements "一只橘猫做饭的搞笑短视频" \
    --target_duration 30 \
    --aspect_ratio "9:16"
"""

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

# ── boilerplate ──────────────────────────────────────────
# Skill 目录结构: scripts/this_script.py → lib/ 是工具库
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"

# project_root 指向 lib/ 目录（包含 custom_tools/, video_workflows/, runtime_aliases/）
project_root = _LIB_DIR
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

load_video_agent_env(_SKILL_DIR)
# ─────────────────────────────────────────────────────────


def str2bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def main():
    parser = argparse.ArgumentParser(description="完整视频生成")
    parser.add_argument("--user_requirements", required=True, help="用户需求描述（必填）")
    parser.add_argument("--target_duration", type=int, default=0, help="目标时长（秒），默认 30，最大 180")
    parser.add_argument("--aspect_ratio", default=None, help="画面比例，默认 9:16")
    parser.add_argument("--platform", default="抖音", help="目标平台，默认 抖音")
    parser.add_argument("--add_subtitles", type=str2bool, default=None, help="是否加字幕，默认 True")
    parser.add_argument("--add_background_music", type=str2bool, default=None, help="是否加 BGM，默认 True")
    parser.add_argument("--generate_social_media_copywriting", type=str2bool, default=True, help="是否生成文案")
    parser.add_argument("--background_music_path", default=None, help="自定义 BGM 路径")
    parser.add_argument("--bgm_volume", type=float, default=None, help="BGM 音量；不传则使用 AI 选择的音量")
    parser.add_argument("--voice_volume", type=float, default=1.5, help="配音音量，默认 1.5")
    parser.add_argument("--video_engine", default=None, help="视频引擎：seedance-fast / seedance / jimeng35pro / veo3")
    parser.add_argument("--enable_image_quality_check", type=str2bool, default=True, help="图片质量检测")
    parser.add_argument("--enable_video_quality_check", type=str2bool, default=True, help="视频质量检测")
    parser.add_argument("--audio_concurrency", type=int, default=3, help="音频并发数")
    parser.add_argument("--user_reference_images", default=None, help="参考图片路径（JSON 列表）")
    parser.add_argument("--douyin_text", default=None, help="抖音参考文本")
    parser.add_argument("--storyboard_only", action="store_true", help="只生成分镜，不执行视频生成")
    parser.add_argument("--capsule", default=None, help="本地 SQLite 胶囊名；会将胶囊合同注入本次生成")
    parser.add_argument("--capsule_db", default="", help="可选胶囊 DB 路径，默认使用 VIDEO_CAPSULE_DB 或项目初始 DB")
    parser.add_argument(
        "--allow_generic_capsule_fallback",
        action="store_true",
        help="允许专用路线胶囊退回普通图生视频预览；默认禁止，以免假冒跑通",
    )

    args = parser.parse_args()
    user_requirements = args.user_requirements
    target_duration = args.target_duration or 30
    capsule = None
    capsule_defaults = {}
    if args.capsule:
        from capsule_runtime import (
            build_capsule_prompt,
            capsule_requires_special_route,
            capsule_runtime_defaults,
            load_capsule,
        )

        capsule = load_capsule(args.capsule, args.capsule_db)
        if capsule_requires_special_route(capsule) and not args.storyboard_only and not args.allow_generic_capsule_fallback:
            raise SystemExit(
                f"Capsule '{args.capsule}' requires a specialized route "
                f"({capsule.get('category')}); use --storyboard_only for planning, "
                "or pass --allow_generic_capsule_fallback only for a non-final preview."
            )
        capsule_defaults = capsule_runtime_defaults(capsule)
        if not args.target_duration and capsule_defaults.get("target_duration"):
            target_duration = capsule_defaults["target_duration"]
        user_requirements = build_capsule_prompt(capsule, user_requirements)

    aspect_ratio = args.aspect_ratio or capsule_defaults.get("aspect_ratio") or "9:16"
    add_subtitles = args.add_subtitles
    if add_subtitles is None:
        add_subtitles = capsule_defaults.get("add_subtitles", True)
    add_background_music = args.add_background_music
    if add_background_music is None:
        add_background_music = capsule_defaults.get("add_background_music", True)
    video_engine = args.video_engine or capsule_defaults.get("video_engine")

    bgm_volume = capsule_defaults.get("bgm_volume")
    if args.bgm_volume is not None:
        bgm_volume = args.bgm_volume

    kwargs = {
        "aspect_ratio": aspect_ratio,
        "platform": args.platform,
        "add_subtitles": add_subtitles,
        "add_background_music": add_background_music,
        "generate_social_media_copywriting": args.generate_social_media_copywriting,
        "voice_volume": capsule_defaults.get("voice_volume", args.voice_volume),
        "enable_image_quality_check": args.enable_image_quality_check,
        "enable_video_quality_check": args.enable_video_quality_check,
        "audio_concurrency": args.audio_concurrency,
    }

    if bgm_volume is not None:
        kwargs["bgm_volume"] = bgm_volume
    background_music_path = args.background_music_path or capsule_defaults.get("background_music_path")
    if background_music_path:
        kwargs["background_music_path"] = background_music_path
    if video_engine:
        kwargs["video_engine"] = video_engine
    if args.user_reference_images:
        kwargs["user_reference_images"] = json.loads(args.user_reference_images)
    if args.douyin_text:
        kwargs["douyin_text"] = args.douyin_text
    if args.storyboard_only:
        kwargs["storyboard_only"] = True
    if capsule:
        kwargs["capsule_name"] = capsule["name"]
        kwargs["capsule_category"] = capsule.get("category")
        kwargs["capsule_config"] = capsule.get("config") or {}

    from video_workflows.general_video.flow import run_general_video_flow

    with contextlib.redirect_stdout(sys.stderr):
        result = run_general_video_flow(
            user_requirements=user_requirements,
            target_duration=target_duration,
            **kwargs,
        )

    if result.get("success") and not args.storyboard_only and result.get("workspace_dir"):
        post_run_warnings = result.setdefault("post_run_warnings", [])
        try:
            from build_edit_plan import write_edit_plan

            edit_plan_path = write_edit_plan(result["workspace_dir"])
            result["edit_plan_path"] = str(edit_plan_path)
        except Exception as exc:
            post_run_warnings.append(f"edit plan build failed: {exc}")

        if result.get("edit_plan_path"):
            try:
                from validate_edit_plan import write_edit_plan_validation, read_json as read_validation_json

                validation_path = write_edit_plan_validation(
                    result["workspace_dir"],
                    edit_plan_path=result["edit_plan_path"],
                )
                result["edit_plan_validation_path"] = str(validation_path)
                edit_plan_validation = read_validation_json(validation_path, {})
                result["edit_plan_validation_ok"] = bool(edit_plan_validation.get("ok"))
                if not edit_plan_validation.get("ok"):
                    post_run_warnings.append("edit plan validation did not pass; see qa/edit_plan_validation.json")
            except Exception as exc:
                post_run_warnings.append(f"edit plan validation failed: {exc}")

        try:
            from argparse import Namespace
            from local_video_qa import run_qa as run_local_video_qa

            workspace = Path(result["workspace_dir"])
            qa_path = workspace / "qa" / "local_video_qa.json"
            qa_args = Namespace(
                run_dir=str(workspace),
                manifest="",
                final_video=str(result.get("final_video") or ""),
                aspect_ratio=aspect_ratio,
                min_duration=max(1.0, min(6.0, float(target_duration) * 0.5)),
                aspect_tolerance=0.08,
                expect_audio=bool((result.get("generation_summary") or {}).get("audio_generated")),
                require_prompts=True,
            )
            local_qa = run_local_video_qa(qa_args)
            qa_path.parent.mkdir(parents=True, exist_ok=True)
            qa_path.write_text(json.dumps(local_qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result["local_video_qa_path"] = str(qa_path)
            result["local_video_qa_ok"] = bool(local_qa.get("ok"))
            if not local_qa.get("ok"):
                post_run_warnings.append("local video QA did not pass; see qa/local_video_qa.json")
        except Exception as exc:
            post_run_warnings.append(f"local video QA failed: {exc}")

        try:
            from plan_repairs import write_repair_plan

            repair_plan_path = write_repair_plan(result["workspace_dir"])
            result["repair_plan_path"] = str(repair_plan_path)
        except Exception as exc:
            post_run_warnings.append(f"repair plan build failed: {exc}")

        try:
            from release_checkpoint import write_release_checkpoint

            checkpoint_path = write_release_checkpoint(
                result["workspace_dir"],
                edit_plan_path=result.get("edit_plan_path"),
                edit_plan_validation_path=result.get("edit_plan_validation_path"),
                repair_plan_path=result.get("repair_plan_path"),
            )
            result["release_checkpoint_path"] = str(checkpoint_path)
        except Exception as exc:
            post_run_warnings.append(f"release checkpoint build failed: {exc}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
