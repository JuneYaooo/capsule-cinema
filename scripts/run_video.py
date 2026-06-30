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

# project_root 指向 lib/ 目录（包含 custom_tools/, video_workflows/, src/）
project_root = _LIB_DIR
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402
from src.video_generation_config import CONFIG  # noqa: E402

load_video_agent_env(_SKILL_DIR)
# ─────────────────────────────────────────────────────────


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _augment_artifact_manifest(
    workspace: Path,
    *,
    delivery_promise: dict,
    preflight_report_path: str = "",
    execution_plan_path: str = "",
    production_proposal_path: str = "",
    decision_log_path: str = "",
    source_review_path: str = "",
    reference_analysis_path: str = "",
) -> None:
    manifest_path = workspace / "artifact_manifest.json"
    manifest = _read_json(manifest_path, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.setdefault("schema_version", 1)
    manifest.setdefault("workflow", "general_video")
    manifest["delivery_promise"] = delivery_promise
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []

    seen = {
        (item.get("category"), item.get("path"))
        for item in artifacts
        if isinstance(item, dict)
    }

    def add(category: str, path_value: str, title: str) -> None:
        if not path_value:
            return
        path = Path(path_value).expanduser()
        if not path.exists():
            return
        key = (category, str(path))
        if key in seen:
            return
        seen.add(key)
        artifacts.append({
            "category": category,
            "path": str(path),
            "title": title,
            "size_bytes": path.stat().st_size,
        })

    add("production_proposal", production_proposal_path, "Production proposal")
    add("decision_log", decision_log_path, "Decision log")
    add("preflight_report", preflight_report_path, "Capsule preflight report")
    add("execution_plan", execution_plan_path, "Capsule execution plan")
    add("source_media_review", source_review_path, "Source media review")
    add("reference_analysis", reference_analysis_path, "Reference analysis")
    manifest["artifacts"] = artifacts
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def str2bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def apply_post_run_delivery_status(result: dict, *, storyboarding_only: bool = False) -> dict:
    """Annotate pipeline success separately from final-video deliverability."""
    qa_blockers: list[str] = []
    if not result.get("success"):
        result["deliverable"] = False
        result["run_status"] = "generation_failed"
        result["qa_blockers"] = qa_blockers
        return result

    if storyboarding_only:
        result["deliverable"] = False
        result["run_status"] = "storyboard_only"
        result["qa_blockers"] = qa_blockers
        return result

    if not result.get("final_video"):
        qa_blockers.append("final_video_missing")
    if result.get("edit_plan_validation_ok") is not True:
        qa_blockers.append("edit_plan_validation_failed")
    if result.get("local_video_qa_ok") is not True:
        qa_blockers.append("local_video_qa_failed")

    checkpoint_path = result.get("release_checkpoint_path")
    if checkpoint_path:
        checkpoint = _read_json(Path(checkpoint_path), {})
        checkpoint_status = checkpoint.get("status") if isinstance(checkpoint, dict) else ""
        result["release_checkpoint_status"] = checkpoint_status
        if checkpoint_status and checkpoint_status != "pass":
            qa_blockers.append("release_checkpoint_not_pass")

    result["qa_blockers"] = sorted(set(qa_blockers))
    result["deliverable"] = not result["qa_blockers"]
    result["run_status"] = "deliverable" if result["deliverable"] else "generated_but_failed_qa"
    return result


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
    parser.add_argument("--image_engine", default=None, help="图片引擎：gpt-image-2 / gpt-image-2-pro / seedream5 / gemini3_pro（默认 gpt-image-2）")
    parser.add_argument("--video_engine", default=None, help="视频引擎：seedance-fast / seedance / seedance2.0 / jimeng35pro / veo3 / veo3.1")
    parser.add_argument("--enable_image_quality_check", type=str2bool, default=True, help="图片质量检测")
    parser.add_argument("--enable_video_quality_check", type=str2bool, default=True, help="视频质量检测")
    parser.add_argument("--audio_concurrency", type=int, default=3, help="音频并发数")
    parser.add_argument("--user_reference_images", default=None, help="参考图片路径（JSON 列表）")
    parser.add_argument("--douyin_text", default=None, help="抖音参考文本")
    parser.add_argument("--storyboard_only", action="store_true", help="只生成分镜，不执行视频生成")
    parser.add_argument("--capsule", default=None, help="本地 SQLite 胶囊短名；会将胶囊合同注入本次生成")
    parser.add_argument("--capsule_db", default="", help="可选胶囊 DB 路径，默认使用 VIDEO_CAPSULE_DB 或项目初始 DB")
    parser.add_argument("--delivery_promise", default="", help="可选交付承诺：motion_led/source_led/tts_led_explainer/reference_remake/capsule_preset/specialized_route")
    parser.add_argument("--source_review_path", default="", help="source_led 路线的 source_media_review.json 路径")
    parser.add_argument("--reference_analysis_path", default="", help="reference_remake 路线的 reference_analysis/video_analysis_brief 路径")
    parser.add_argument(
        "--allow_generic_capsule_fallback",
        action="store_true",
        help="允许专用路线胶囊退回普通图生视频预览；默认禁止，以免假冒跑通",
    )
    parser.add_argument(
        "--accept_preflight_changes",
        action="store_true",
        help="接受 Preflight 选用合法替代工具或显式降级；未接受时生成阶段会阻止 needs_confirmation 的胶囊",
    )

    args = parser.parse_args()
    user_requirements = args.user_requirements
    target_duration = args.target_duration or 30
    user_reference_images = json.loads(args.user_reference_images) if args.user_reference_images else []
    capsule = None
    capsule_defaults = {}
    capsule_preflight_report = {}
    capsule_execution_plan = {}
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
        user_requirements = build_capsule_prompt(
            capsule,
            user_requirements,
            user_reference_images=user_reference_images,
        )

        config = capsule.get("config") or {}
        if isinstance(config.get("roles"), dict) or isinstance(config.get("output_contract"), dict):
            from src.capsule_preflight import (
                load_all_tools,
                raise_if_blocked,
                run_preflight,
                scan_available_env,
                to_execution_plan,
                to_report,
            )

            preflight_capsule = {
                "name": capsule["name"],
                "roles": config.get("roles", {}),
                "output_contract": config.get("output_contract", {}),
            }
            tools = load_all_tools()
            preflight = run_preflight(preflight_capsule, tools, scan_available_env(dict(os.environ)))
            try:
                raise_if_blocked(preflight, tools)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if preflight.status == "needs_confirmation" and not (args.storyboard_only or args.accept_preflight_changes):
                raise SystemExit(
                    "Capsule Preflight selected a substituted/degraded route; "
                    "rerun with --accept_preflight_changes after reviewing the plan."
                )
            capsule_preflight_report = to_report(preflight)
            capsule_execution_plan = to_execution_plan(preflight, preflight_capsule)

    aspect_ratio = args.aspect_ratio or capsule_defaults.get("aspect_ratio") or "9:16"
    add_subtitles = args.add_subtitles
    if add_subtitles is None:
        add_subtitles = capsule_defaults.get("add_subtitles", True)
    add_background_music = args.add_background_music
    if add_background_music is None:
        add_background_music = capsule_defaults.get("add_background_music", True)
    image_engine = args.image_engine or capsule_defaults.get("image_engine")
    video_engine = args.video_engine or capsule_defaults.get("video_engine")
    force_image_fallback_video = bool(capsule_defaults.get("force_image_fallback_video"))
    video_generation_route = capsule_defaults.get("video_generation_route")

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
    if image_engine:
        kwargs["image_engine"] = image_engine
    if video_engine:
        kwargs["video_engine"] = video_engine
    if force_image_fallback_video:
        kwargs["force_image_fallback_video"] = True
    if video_generation_route:
        kwargs["video_generation_route"] = video_generation_route
    if user_reference_images:
        kwargs["user_reference_images"] = user_reference_images
    if args.douyin_text:
        kwargs["douyin_text"] = args.douyin_text
    if args.storyboard_only:
        kwargs["storyboard_only"] = True
    if capsule:
        kwargs["capsule_name"] = capsule["name"]
        kwargs["capsule_category"] = capsule.get("category")
        kwargs["capsule_config"] = capsule.get("config") or {}
        if capsule_preflight_report:
            kwargs["capsule_preflight_report"] = capsule_preflight_report
        if capsule_execution_plan:
            kwargs["capsule_execution_plan"] = capsule_execution_plan

    from src.contracts.production_contract import (
        append_decision,
        build_delivery_promise,
        build_production_proposal,
        validate_preflight_contract,
        write_production_proposal,
    )

    delivery_promise = build_delivery_promise(
        user_requirements=user_requirements,
        route="capsule" if capsule else "general_video",
        capsule_name=(capsule or {}).get("name", ""),
        capsule_category=(capsule or {}).get("category", ""),
        has_source_media=bool(args.source_review_path),
        has_reference_analysis=bool(args.reference_analysis_path),
        has_reference_material=bool(args.user_reference_images or args.douyin_text),
        needs_audio=bool(add_subtitles) or bool(kwargs.get("voice_volume")),
        explicit=args.delivery_promise,
        approved_fallback="generic_preview" if args.allow_generic_capsule_fallback else "",
    )
    validate_preflight_contract(
        delivery_promise,
        source_review_path=args.source_review_path,
        reference_analysis_path=args.reference_analysis_path,
        has_reference_material=bool(args.user_reference_images or args.douyin_text),
        storyboarding_only=bool(args.storyboard_only),
        allow_generic_fallback=bool(args.allow_generic_capsule_fallback),
    )
    kwargs["delivery_promise"] = delivery_promise
    if args.source_review_path:
        kwargs["source_review_path"] = args.source_review_path
    if args.reference_analysis_path:
        kwargs["reference_analysis_path"] = args.reference_analysis_path

    from video_workflows.general_video.flow import run_general_video_flow

    with contextlib.redirect_stdout(sys.stderr):
        result = run_general_video_flow(
            user_requirements=user_requirements,
            target_duration=target_duration,
            **kwargs,
        )

    if result.get("workspace_dir"):
        workspace = Path(result["workspace_dir"])
        result["delivery_promise"] = delivery_promise
        if capsule and capsule_execution_plan:
            try:
                workspace.mkdir(parents=True, exist_ok=True)
                report_path = workspace / "preflight_report.json"
                plan_path = workspace / "execution_plan.json"
                report_path.write_text(
                    json.dumps(capsule_preflight_report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                plan_path.write_text(
                    json.dumps(capsule_execution_plan, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                result["preflight_report_path"] = str(report_path)
                result["execution_plan_path"] = str(plan_path)
            except Exception as exc:
                result.setdefault("post_run_warnings", []).append(f"preflight artifact write failed: {exc}")
        try:
            proposal = build_production_proposal(
                user_requirements=user_requirements,
                delivery_promise=delivery_promise,
                route="capsule" if capsule else "general_video",
                aspect_ratio=aspect_ratio,
                target_duration=target_duration,
                platform=args.platform,
                audio_strategy="tts_or_narration" if delivery_promise.get("promise_type") == "tts_led_explainer" else "runtime_planned",
                tool_route={
                    "video_engine": "image-fallback" if force_image_fallback_video else (video_engine or "runtime_selection"),
                    "image_engine": image_engine or CONFIG.DEFAULT_IMAGE_ENGINE,
                    "tts": "UniversalTTSTool",
                    "bgm": "online_or_generated" if add_background_music else "none",
                },
                risks=[],
                release_bar=[
                    "artifact_manifest.json present",
                    "local_video_qa.json passes",
                    "release_checkpoint.json passes",
                    "delivery promise honored",
                ],
                source_review_path=args.source_review_path,
                reference_analysis_path=args.reference_analysis_path,
            )
            proposal_path = write_production_proposal(workspace, proposal)
            result["production_proposal_path"] = str(proposal_path)
            decision_path = append_decision(
                workspace,
                category="delivery_promise",
                selected=delivery_promise.get("promise_type", ""),
                options_considered=[
                    "motion_led",
                    "source_led",
                    "tts_led_explainer",
                    "reference_remake",
                    "capsule_preset",
                    "specialized_route",
                ],
                reason="Selected before generation from route, capsule, source/reference hints, and audio strategy.",
                user_visible=True,
                user_approved=not args.storyboard_only,
                confidence=0.75,
                qa_impact="Release checkpoint validates promise-specific blockers.",
            )
            result["decision_log_path"] = str(decision_path)
            selected_video_route = "image-fallback" if force_image_fallback_video else video_engine
            if selected_video_route:
                append_decision(
                    workspace,
                    category="provider_selection",
                    selected=selected_video_route,
                    options_considered=["image-fallback", "seedance-fast", "seedance", "seedance2.0", "jimeng35pro", "veo3", "veo3.1"],
                    reason="Video engine was specified by CLI argument or capsule runtime defaults.",
                    user_visible=True,
                    user_approved=True,
                    confidence=0.8,
                    qa_impact="Video QA and release checkpoint must verify output quality.",
                )
        except Exception as exc:
            result.setdefault("post_run_warnings", []).append(f"production contract write failed: {exc}")

        try:
            _augment_artifact_manifest(
                workspace,
                delivery_promise=delivery_promise,
                preflight_report_path=result.get("preflight_report_path", ""),
                execution_plan_path=result.get("execution_plan_path", ""),
                production_proposal_path=result.get("production_proposal_path", ""),
                decision_log_path=result.get("decision_log_path", ""),
                source_review_path=args.source_review_path,
                reference_analysis_path=args.reference_analysis_path,
            )
            result["artifact_manifest_path"] = str(workspace / "artifact_manifest.json")
        except Exception as exc:
            result.setdefault("post_run_warnings", []).append(f"artifact manifest contract update failed: {exc}")

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

    apply_post_run_delivery_status(result, storyboarding_only=bool(args.storyboard_only))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
