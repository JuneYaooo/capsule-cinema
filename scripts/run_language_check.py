#!/usr/bin/env python3
"""视频语音语言检测 + 自动重生成。

设计用于 jimeng3.5pro 等模型：每个分镜生成后立即检测语音语言，
不通过则自动重生成（最多 max_retries 次），并记录完整日志。

核心函数（供外部脚本调用）：
    check_and_regen_single(video_path, image_path, video_prompt, ...)
        -> 检测单个 5s 分镜视频，不通过自动重生成，返回最终视频路径

命令行用法：
    # 单个分镜检测 + 重生成
    python run_language_check.py \
      --video_path /path/to/scene_01.mp4 \
      --expected_language zh \
      --auto_regen \
      --image_path /path/to/scene_01.png \
      --video_prompt "prompt..." \
      --max_retries 2

    # 仅检测（不重生成）
    python run_language_check.py \
      --video_path /path/to/scene_01.mp4 \
      --expected_language zh

    # 批量检测 workspace
    python run_language_check.py \
      --workspace_dir output/<run_id> \
      --expected_language zh \
      --auto_regen --max_retries 2
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

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

load_video_agent_env(_SKILL_DIR)

from src.contracts import get_storyboard_scenes, scene_id_candidates  # noqa: E402
# ─────────────────────────────────────────────────────────

# ── logging ──────────────────────────────────────────────
logger = logging.getLogger("language_check")
logger.setLevel(logging.DEBUG)

# console handler (INFO)
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_ch)

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
}


def _setup_file_logger(log_dir: str):
    """添加文件日志 handler，记录 DEBUG 级别完整日志。"""
    log_path = Path(log_dir) / f"language_check_{datetime.now():%Y%m%d_%H%M%S}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    logger.info(f"📝 日志文件: {log_path}")
    return str(log_path)


# ── 音频提取 ─────────────────────────────────────────────

def extract_audio(video_path: str, audio_path: str) -> bool:
    """用 ffmpeg 从视频中提取音频。"""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and Path(audio_path).exists()
    except Exception as e:
        logger.warning(f"  ⚠️ 音频提取失败: {e}")
        return False


# ── 语言检测 ─────────────────────────────────────────────

def detect_language(audio_path: str, model_size: str = "tiny") -> dict:
    """用硅基流动 SenseVoiceSmall API 转录音频。
    回退：若 API 不可用则用本地 whisper。

    Returns:
        {
            "language": "zh" | "en" | "unknown",
            "text": "转录文本",
            "chinese_ratio": 0.95,
            "english_ratio": 0.03,
        }
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    api_base = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")

    full_text = None

    # 优先用硅基流动 API
    if api_key:
        try:
            import requests
            with open(audio_path, 'rb') as f:
                files = {'file': (Path(audio_path).name, f, 'audio/mpeg')}
                data = {'model': 'FunAudioLLM/SenseVoiceSmall'}
                headers = {'Authorization': f'Bearer {api_key}'}
                response = requests.post(
                    f"{api_base}/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120,
                )
            if response.status_code == 200:
                result = response.json()
                full_text = result.get('text', '').strip()
                logger.info(f"  📡 SiliconFlow SenseVoice 转录完成")
                logger.debug(f"  转录原文: {full_text}")
            else:
                logger.warning(f"  ⚠️ SiliconFlow API 错误 ({response.status_code})，回退到本地 whisper")
        except Exception as e:
            logger.warning(f"  ⚠️ SiliconFlow API 调用失败: {e}，回退到本地 whisper")

    # 回退：本地 whisper
    if full_text is None:
        try:
            import whisper
            model = whisper.load_model(model_size)
            result = model.transcribe(audio_path, word_timestamps=False, verbose=False)
            full_text = result.get("text", "").strip()
            logger.info(f"  🔧 本地 Whisper ({model_size}) 转录完成")
            logger.debug(f"  转录原文: {full_text}")
        except ImportError:
            logger.error("  ❌ 无法转录：SILICONFLOW_API_KEY 未设置且 whisper 未安装")
            return {"language": "unknown", "text": "", "chinese_ratio": 0, "english_ratio": 0}

    if not full_text:
        full_text = ""

    # 计算中英文字符占比（只看纯中英文字符，过滤 emoji/标点/数字/空格）
    if full_text:
        chinese_chars = sum(1 for c in full_text if '\u4e00' <= c <= '\u9fff')
        english_chars = sum(1 for c in full_text if 'a' <= c.lower() <= 'z')
        lang_chars = chinese_chars + english_chars
        chinese_ratio = chinese_chars / lang_chars if lang_chars else 0
        english_ratio = english_chars / lang_chars if lang_chars else 0
    else:
        chinese_ratio = 0
        english_ratio = 0

    # 根据占比推断语言
    if chinese_ratio >= 0.5:
        detected_lang = "zh"
    elif english_ratio >= 0.5:
        detected_lang = "en"
    else:
        detected_lang = "unknown"

    return {
        "language": detected_lang,
        "text": full_text,
        "chinese_ratio": round(chinese_ratio, 3),
        "english_ratio": round(english_ratio, 3),
    }


def is_target_language(detection: dict, expected: str) -> bool:
    """判断检测结果是否为目标语言。阈值 50%。"""
    if expected == "zh":
        return detection["chinese_ratio"] >= 0.5
    if expected == "en":
        return detection["english_ratio"] >= 0.5
    return detection["language"] == expected


# ── 单视频检测 ───────────────────────────────────────────

def check_video_language(video_path: str, expected_language: str = "zh",
                         whisper_model: str = "tiny") -> dict:
    """检测单个视频的语音语言。"""
    logger.info(f"  🔍 检测语言: {Path(video_path).name}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_audio = tmp.name

    try:
        if not extract_audio(video_path, tmp_audio):
            logger.warning(f"  ⚠️ 无法提取音频，跳过检测")
            return {"video_path": video_path, "passed": True,
                    "detected_language": "unknown", "text": "",
                    "chinese_ratio": 0, "english_ratio": 0, "skipped": True}

        if Path(tmp_audio).stat().st_size < 1024:
            logger.warning(f"  ⚠️ 音频为空（无声视频），跳过检测")
            return {"video_path": video_path, "passed": True,
                    "detected_language": "silent", "text": "",
                    "chinese_ratio": 0, "english_ratio": 0, "skipped": True}

        detection = detect_language(tmp_audio, model_size=whisper_model)
        passed = is_target_language(detection, expected_language)

        expected_name = LANGUAGE_NAMES.get(expected_language, expected_language)
        detected_name = LANGUAGE_NAMES.get(detection["language"], detection["language"])
        ratio_info = f"中文: {detection['chinese_ratio']:.0%}, 英文: {detection['english_ratio']:.0%}"

        if passed:
            logger.info(f"  ✅ 语言正确: {detected_name} ({ratio_info})")
        else:
            logger.info(f"  ❌ 语言错误: 期望{expected_name}，检测到{detected_name} ({ratio_info})")
            if detection["text"]:
                logger.info(f"     转录预览: {detection['text'][:80]}...")

        return {
            "video_path": video_path,
            "passed": passed,
            "detected_language": detection["language"],
            "chinese_ratio": detection["chinese_ratio"],
            "english_ratio": detection["english_ratio"],
            "text": detection["text"],
        }
    finally:
        if Path(tmp_audio).exists():
            os.unlink(tmp_audio)


# ── 视频重生成 ───────────────────────────────────────────

def regenerate_video(image_path: str, video_prompt: str, output_path: str,
                     engine: str = "jimeng35pro",
                     aspect_ratio: str = "16:9") -> Optional[str]:
    """重新生成视频。"""
    logger.debug(f"  重生成参数:")
    logger.debug(f"    engine: {engine}")
    logger.debug(f"    image_path: {image_path}")
    logger.debug(f"    prompt: {video_prompt}")
    logger.debug(f"    aspect_ratio: {aspect_ratio}")

    if engine == "jimeng35pro":
        from custom_tools.video_generation.jimeng35pro_video_generator_tool import (
            Jimeng35ProVideoGeneratorTool,
        )
        tool = Jimeng35ProVideoGeneratorTool()
        result = tool._run(
            prompt=video_prompt,
            generation_type="image_to_video",
            image_path=image_path,
            output_dir=str(Path(output_path).parent),
            aspect_ratio=aspect_ratio,
        )
    elif engine == "veo3":
        from custom_tools.video_generation.veo3_video_generator_tool import (
            Veo3VideoGeneratorTool,
        )
        tool = Veo3VideoGeneratorTool()
        result = tool._run(
            prompt=video_prompt,
            generation_type="image_to_video",
            image_path=image_path,
            output_dir=str(Path(output_path).parent),
            aspect_ratio=aspect_ratio,
        )
    else:
        raise ValueError(f"Unsupported video engine: {engine}. Supported: jimeng35pro, veo3")

    if isinstance(result, dict):
        new_path = result.get("output_path")
    else:
        new_path = str(result) if result else None

    if new_path:
        logger.debug(f"  重生成输出: {new_path}")
    return new_path


# ── 核心：检测 + 重生成（单个分镜）─────────────────────

def check_and_regen_single(
    video_path: str,
    image_path: str,
    video_prompt: str,
    expected_language: str = "zh",
    max_retries: int = 2,
    engine: str = "jimeng35pro",
    aspect_ratio: str = "16:9",
    whisper_model: str = "tiny",
    scene_index: Optional[int] = None,
    log_dir: Optional[str] = None,
) -> dict:
    """检测单个分镜视频语言，不通过则自动重生成。

    这是主要的对外接口，设计用于每个 jimeng3.5pro 分镜生成后立即调用。

    Args:
        video_path: 生成的视频路径
        image_path: 源图片路径（重生成时需要）
        video_prompt: 完整的视频 prompt（重生成时需要，也会记录到日志）
        expected_language: 期望语言 zh/en
        max_retries: 最大重试次数（默认 2，即最多生成 3 次）
        engine: 视频引擎
        aspect_ratio: 画面比例
        whisper_model: whisper 模型大小
        scene_index: 分镜序号（用于日志）
        log_dir: 日志目录（不传则不写文件日志）

    Returns:
        {
            "final_video_path": str,
            "passed": bool,
            "attempts": int,
            "history": [{"attempt": 1, "passed": bool, "chinese_ratio": float, ...}, ...],
        }
    """
    if log_dir:
        _setup_file_logger(log_dir)

    scene_label = f"分镜 {scene_index}" if scene_index is not None else Path(video_path).stem
    logger.info(f"\n{'─'*50}")
    logger.info(f"🎬 {scene_label} 语言检测")
    logger.debug(f"  video_path: {video_path}")
    logger.debug(f"  image_path: {image_path}")
    logger.debug(f"  video_prompt: {video_prompt}")
    logger.debug(f"  engine: {engine}, expected: {expected_language}, max_retries: {max_retries}")

    history = []
    current_video = video_path

    for attempt in range(1, max_retries + 2):
        logger.info(f"  📋 第 {attempt} 次检测 ({Path(current_video).name})")

        result = check_video_language(current_video, expected_language, whisper_model)
        history.append({
            "attempt": attempt,
            "video_path": current_video,
            "passed": result.get("passed", False),
            "detected_language": result.get("detected_language"),
            "chinese_ratio": result.get("chinese_ratio", 0),
            "english_ratio": result.get("english_ratio", 0),
            "text": result.get("text", ""),
        })

        if result.get("passed"):
            logger.info(f"  🎉 {scene_label} 通过 (第 {attempt} 次)")
            return {
                "final_video_path": current_video,
                "passed": True,
                "attempts": attempt,
                "history": history,
            }

        if attempt > max_retries:
            logger.warning(f"  ⚠️ {scene_label} 已达最大重试次数 ({max_retries})，放弃")
            break

        logger.info(f"  🔄 {scene_label} 第 {attempt} 次重生成...")
        logger.debug(f"  重生成 prompt: {video_prompt}")

        new_video = regenerate_video(
            image_path=image_path,
            video_prompt=video_prompt,
            output_path=current_video,
            engine=engine,
            aspect_ratio=aspect_ratio,
        )

        if new_video and Path(new_video).exists():
            current_video = new_video
            logger.info(f"  ✅ 重生成完成: {Path(new_video).name}")
        else:
            logger.error(f"  ❌ 重生成失败")
            break

    return {
        "final_video_path": current_video,
        "passed": False,
        "attempts": len(history),
        "history": history,
    }


# ── 批量检测 workspace ───────────────────────────────────

def batch_check_workspace(workspace_dir: str, expected_language: str = "zh",
                          auto_regen: bool = False, max_retries: int = 2,
                          engine: str = "jimeng35pro",
                          whisper_model: str = "tiny") -> dict:
    """批量检测 workspace 下所有视频的语言。"""
    workspace = Path(workspace_dir)
    videos_dir = workspace / "work" / "videos"
    log_dir = str(workspace / "logs")

    _setup_file_logger(log_dir)

    if not videos_dir.exists():
        logger.error(f"❌ 视频目录不存在: {videos_dir}")
        return {"error": "videos directory not found"}

    # 尝试加载 storyboard
    storyboard = None
    sb_path = workspace / "storyboard.json"
    if sb_path.exists():
        with open(sb_path, "r", encoding="utf-8") as f:
            storyboard = json.load(f)
        logger.info(f"📋 已加载 storyboard.json ({len(get_storyboard_scenes(storyboard))} 个分镜)")

    video_files = sorted(videos_dir.glob("*.mp4"))
    if not video_files:
        logger.error(f"❌ 没有找到视频文件")
        return {"error": "no video files found"}

    expected_name = LANGUAGE_NAMES.get(expected_language, expected_language)
    logger.info(f"\n🎬 检测 {len(video_files)} 个视频 (期望: {expected_name})\n")

    results = []
    failed = []

    for vf in video_files:
        if auto_regen and storyboard:
            scene_info = _find_scene_for_video(storyboard, vf)
            if scene_info:
                result = check_and_regen_single(
                    video_path=str(vf),
                    image_path=scene_info.get("image_path", ""),
                    video_prompt=scene_info.get("video_prompt", ""),
                    expected_language=expected_language,
                    max_retries=max_retries,
                    engine=engine,
                    aspect_ratio=storyboard.get("aspect_ratio", "16:9"),
                    whisper_model=whisper_model,
                    scene_index=scene_info.get("index", scene_info.get("scene_id")),
                    log_dir=None,  # 已经 setup 过了
                )
                results.append(result)
                if not result["passed"]:
                    failed.append(vf.name)
                continue

        result = check_video_language(str(vf), expected_language, whisper_model)
        results.append(result)
        if not result.get("passed"):
            failed.append(vf.name)

    total = len(results)
    passed_count = total - len(failed)
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 检测结果: {passed_count}/{total} 通过")
    if failed:
        logger.info(f"❌ 未通过: {', '.join(failed)}")
    logger.info(f"{'='*50}")

    return {
        "total": total,
        "passed": passed_count,
        "failed": failed,
        "results": results,
    }


def _find_scene_for_video(storyboard: dict, video_path: Path) -> Optional[dict]:
    """从 storyboard 中找到视频对应的分镜信息。"""
    video_name = video_path.stem

    for fallback, scene in enumerate(get_storyboard_scenes(storyboard), start=1):
        for idx in scene_id_candidates(scene, fallback):
            if f"scene_{idx:02d}" in video_name:
                return scene

    return None


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="视频语音语言检测 + 自动重生成")
    parser.add_argument("--video_path", default=None, help="单个视频路径")
    parser.add_argument("--workspace_dir", default=None, help="workspace 目录（批量检测）")
    parser.add_argument("--expected_language", default="zh", help="期望语言（zh/en/ja/ko），默认 zh")
    parser.add_argument("--auto_regen", action="store_true", help="语言不符时自动重生成")
    parser.add_argument("--image_path", default=None, help="源图片路径（单视频重生成时需要）")
    parser.add_argument("--video_prompt", default=None, help="视频 prompt（单视频重生成时需要）")
    parser.add_argument("--max_retries", type=int, default=2, help="最大重试次数，默认 2")
    parser.add_argument("--video_engine", default="jimeng35pro", help="视频引擎，默认 jimeng35pro")
    parser.add_argument("--aspect_ratio", default="16:9", help="画面比例，默认 16:9")
    parser.add_argument("--whisper_model", default="tiny", help="Whisper 模型大小，默认 tiny")
    parser.add_argument("--log_dir", default=None, help="日志目录（不传则只输出到控制台）")
    args = parser.parse_args()

    if not args.video_path and not args.workspace_dir:
        parser.error("必须指定 --video_path 或 --workspace_dir")

    if args.workspace_dir:
        result = batch_check_workspace(
            workspace_dir=args.workspace_dir,
            expected_language=args.expected_language,
            auto_regen=args.auto_regen,
            max_retries=args.max_retries,
            engine=args.video_engine,
            whisper_model=args.whisper_model,
        )
    elif args.auto_regen:
        if not args.image_path or not args.video_prompt:
            parser.error("自动重生成需要 --image_path 和 --video_prompt")
        result = check_and_regen_single(
            video_path=args.video_path,
            image_path=args.image_path,
            video_prompt=args.video_prompt,
            expected_language=args.expected_language,
            max_retries=args.max_retries,
            engine=args.video_engine,
            aspect_ratio=args.aspect_ratio,
            whisper_model=args.whisper_model,
            log_dir=args.log_dir,
        )
    else:
        if args.log_dir:
            _setup_file_logger(args.log_dir)
        result = check_video_language(
            video_path=args.video_path,
            expected_language=args.expected_language,
            whisper_model=args.whisper_model,
        )

    print(f"\n{json.dumps(result, ensure_ascii=False, indent=2, default=str)}")


if __name__ == "__main__":
    main()
