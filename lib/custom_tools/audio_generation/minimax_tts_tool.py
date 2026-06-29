"""MiniMax T2A v2 TTS fallback。

当豆包 TTS 因账号未开通某音色（HTTP 403 / code 3001）而失败时，
本模块用 MiniMax T2A v2 兜底产出 mp3，避免整个视频管线中断。

只暴露一个轻量函数 ``synthesize_with_minimax``，被
``UniversalTTSTool._synthesize_with_doubao`` 在豆包失败时调用。
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

import requests

from src.logger import get_logger

logger = get_logger("minimax_tts_tool")

_MINIMAX_ENDPOINT = "https://api.minimax.chat/v1/t2a_v2"
_DEFAULT_VOICE_MAP = {
    # 6.22 life_sim historical alias -> MiniMax narrator voice
    "male_narrator": "audiobook_male_2",
    # 豆包女声 → MiniMax 近似女声
    "zh_female_shuangkuaisisi_moon_bigtts": "female-shaonv",
    "zh_female_tianmeixiaoyuan_moon_bigtts": "female-yujie",
    # 豆包男声 → MiniMax 近似男声
    "zh_male_chunhou_moon_bigtts": "male-qn-jingying",
    "zh_male_jieshuoxiaoming_moon_bigtts": "audiobook_male_2",
    "zh_male_xuefeng_mars_bigtts": "male-qn-jingying",
    "zh_male_sunwukong_mars_bigtts": "male-qn-daxuesheng",
    "zh_male_narrator_mars_bigtts": "audiobook_male_2",
    "zh_male_warm_mars_bigtts": "male-qn-jingying",
    "zh_female_peiqi_mars_bigtts": "female-shaonv",
    "zh_female_gentle_mars_bigtts": "female-yujie",
    "zh_female_sweet_mars_bigtts": "female-shaonv",
    "zh_female_narrator_mars_bigtts": "audiobook_female_1",
}


def _resolve_minimax_voice_id(voice_type: str = "") -> str:
    """Resolve a generic voice_type into the MiniMax voice_id sent to T2A.

    Doubao-style ids are mapped to known MiniMax fallbacks, while MiniMax-native
    ids such as ``Chinese (Mandarin)_Radio_Host`` or ``male-qn-daxuesheng`` are
    passed through unchanged.
    """
    candidate = str(voice_type or "").strip()
    if not candidate:
        return "audiobook_male_2"
    if candidate in _DEFAULT_VOICE_MAP:
        return _DEFAULT_VOICE_MAP[candidate]
    if candidate.startswith("zh_"):
        return "audiobook_male_2"
    return candidate


def _extract_group_id(api_key: str) -> Optional[str]:
    try:
        payload = api_key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded.get("GroupID")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"⚠️ 解析 MinIMax JWT 失败: {exc}")
        return None


def synthesize_with_minimax(
    text: str,
    output_path: str,
    voice_type: str = "",
    speed: float = 1.0,
) -> dict:
    """用 MiniMax T2A v2 合成 mp3，写入 ``output_path``。

    返回与 UniversalTTSTool 一致的结构：
        {"success": bool, "output_path": str, "provider": "minimax", "error": str?}
    """
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        return {"success": False, "provider": "minimax", "error": "MINIMAX_API_KEY 未设置"}

    group_id = os.getenv("MINIMAX_GROUP_ID") or _extract_group_id(api_key)
    if not group_id:
        return {"success": False, "provider": "minimax", "error": "无法确定 MiniMax GroupID"}

    voice_id = _resolve_minimax_voice_id(voice_type)

    try:
        speed_clamped = max(0.5, min(2.0, float(speed) if speed else 1.0))
    except (TypeError, ValueError):
        speed_clamped = 1.0

    body = {
        "model": "speech-01-turbo",
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed_clamped,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{_MINIMAX_ENDPOINT}?GroupId={group_id}"

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        if response.status_code != 200:
            return {
                "success": False,
                "provider": "minimax",
                "error": f"HTTP {response.status_code}: {response.text[:300]}",
            }

        result = response.json()
        base_resp = result.get("base_resp") or {}
        if base_resp.get("status_code") != 0:
            return {
                "success": False,
                "provider": "minimax",
                "error": f"MiniMax 错误: {base_resp}",
            }

        audio_hex = (result.get("data") or {}).get("audio")
        if not audio_hex:
            return {"success": False, "provider": "minimax", "error": "返回中未找到音频数据"}

        # MiniMax T2A v2 返回的是 hex 字符串
        try:
            audio_bytes = bytes.fromhex(audio_hex)
        except ValueError:
            audio_bytes = base64.b64decode(audio_hex)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as f:
            f.write(audio_bytes)

        logger.info(
            f"🎙️ MiniMax TTS 成功: voice={voice_id} -> {out} ({len(audio_bytes)/1024:.1f}KB)"
        )
        return {"success": True, "provider": "minimax", "output_path": str(out)}

    except requests.RequestException as exc:
        return {"success": False, "provider": "minimax", "error": f"网络异常: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "provider": "minimax", "error": f"未知异常: {exc}"}
