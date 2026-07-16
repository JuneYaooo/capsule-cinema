"""Official Doubao Speech TTS 2.0 bidirectional WebSocket adapter."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional, Type

from pydantic import BaseModel, Field

from .base_tool_compat import BaseTool
from .doubao_tts_protocol import EventType, Message, MessageType, client_event


DEFAULT_WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DEFAULT_MODEL = "seed-tts-2.0-standard"
DEFAULT_SPEAKER = "zh_female_gaolengyujie_uranus_bigtts"
SUPPORTED_FORMATS = {"mp3", "pcm", "ogg_opus", "wav"}
SUPPORTED_SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}
SPEAKER_ALIASES = {
    "science_female": DEFAULT_SPEAKER,
    "female_default": DEFAULT_SPEAKER,
    "science_male": "zh_male_jieshuoxiaoming_uranus_bigtts",
    "male_default": "zh_male_jieshuoxiaoming_uranus_bigtts",
    "zh_male_sunwukong_mars_bigtts": "zh_male_sunwukong_uranus_bigtts",
    "zh_male_qingxian": "zh_male_jieshuoxiaoming_uranus_bigtts",
    "zh_male_lanxiaoyang_mars_bigtts": "zh_male_lanyinmianbao_uranus_bigtts",
}


class DoubaoTTSSchema(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    output_path: Optional[str] = Field(None, description="Local output audio path")
    speaker: Optional[str] = Field(None, description="Doubao Speech 2.0 speaker ID")
    voice_type: Optional[str] = Field(None, description="Backward-compatible alias for speaker")
    speed_ratio: float = Field(1.0, description="Playback speed ratio, 0.5 to 2.0")
    encoding: str = Field("mp3", description="mp3, pcm, ogg_opus, or wav")
    sample_rate: int = Field(24000, description="Audio sample rate in Hz")
    bit_rate: int = Field(128000, description="MP3 bit rate in bps")
    loudness_rate: int = Field(0, description="Loudness adjustment, -50 to 100")
    enable_subtitle: bool = Field(False, description="Return word-level subtitle timestamps")
    context_texts: Optional[list[str]] = Field(None, description="Speech style instructions")
    section_id: Optional[str] = Field(None, description="Multi-turn synthesis context ID")
    explicit_language: Optional[str] = Field(None, description="Explicit synthesis language")
    explicit_dialect: Optional[str] = Field(None, description="Explicit dialect")
    pitch: int = Field(0, description="Pitch adjustment, -12 to 12")
    disable_markdown_filter: bool = Field(True, description="Parse and remove Markdown syntax")
    disable_emoji_filter: bool = Field(False, description="Enable emoji parsing/filtering")
    aigc_watermark: bool = Field(False, description="Append an audible AIGC marker")
    timeout_seconds: int = Field(180, description="Overall synthesis timeout")


class DoubaoTTSTool(BaseTool):
    name: str = "豆包语音合成工具"
    description: str = (
        "通过豆包语音官方 API Key 和 seed-tts-2.0 双向 WebSocket 接口合成语音，"
        "支持流式音频、语音指令和字级时间戳。"
    )
    args_schema: Type[BaseModel] = DoubaoTTSSchema

    def _run(
        self,
        text: str,
        output_path: Optional[str] = None,
        speaker: Optional[str] = None,
        voice_type: Optional[str] = None,
        speed_ratio: float = 1.0,
        encoding: str = "mp3",
        sample_rate: int = 24000,
        bit_rate: int = 128000,
        loudness_rate: int = 0,
        enable_subtitle: bool = False,
        context_texts: Optional[list[str]] = None,
        section_id: Optional[str] = None,
        explicit_language: Optional[str] = None,
        explicit_dialect: Optional[str] = None,
        pitch: int = 0,
        disable_markdown_filter: bool = True,
        disable_emoji_filter: bool = False,
        aigc_watermark: bool = False,
        timeout_seconds: int = 180,
        **_: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("DOUBAO_TTS_API_KEY")
        if not api_key:
            return {
                "success": False,
                "provider": "doubao",
                "error": "Missing required env vars: DOUBAO_TTS_API_KEY",
            }
        if not text or not text.strip():
            return {
                "success": False,
                "provider": "doubao",
                "error": "Doubao TTS 2.0 requires non-empty text",
            }

        audio_format = encoding.strip().lower()
        if audio_format not in SUPPORTED_FORMATS:
            return {"success": False, "provider": "doubao", "error": f"Unsupported audio format: {encoding}"}
        if sample_rate not in SUPPORTED_SAMPLE_RATES:
            return {"success": False, "provider": "doubao", "error": f"Unsupported sample rate: {sample_rate}"}
        if not 0.5 <= speed_ratio <= 2.0:
            return {"success": False, "provider": "doubao", "error": "speed_ratio must be between 0.5 and 2.0"}
        if not -50 <= loudness_rate <= 100:
            return {"success": False, "provider": "doubao", "error": "loudness_rate must be between -50 and 100"}
        if not -12 <= pitch <= 12:
            return {"success": False, "provider": "doubao", "error": "pitch must be between -12 and 12"}

        selected_speaker = speaker or voice_type or os.getenv("DOUBAO_TTS_SPEAKER") or DEFAULT_SPEAKER
        selected_speaker = SPEAKER_ALIASES.get(selected_speaker, selected_speaker)
        destination = Path(output_path).expanduser() if output_path else Path(
            f"output/manual_tool/work/audios/doubao_{uuid.uuid4().hex[:8]}.{audio_format}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)

        request_params = self._request_params(
            text=text,
            speaker=selected_speaker,
            speed_ratio=speed_ratio,
            encoding=audio_format,
            sample_rate=sample_rate,
            bit_rate=bit_rate,
            loudness_rate=loudness_rate,
            enable_subtitle=enable_subtitle,
            context_texts=context_texts,
            section_id=section_id,
            explicit_language=explicit_language,
            explicit_dialect=explicit_dialect,
            pitch=pitch,
            disable_markdown_filter=disable_markdown_filter,
            disable_emoji_filter=disable_emoji_filter,
            aigc_watermark=aigc_watermark,
        )
        try:
            return asyncio.run(
                asyncio.wait_for(
                    self._synthesize(api_key=api_key, request_params=request_params, destination=destination),
                    timeout=max(10, timeout_seconds),
                )
            )
        except TimeoutError:
            return {"success": False, "provider": "doubao", "error": "Doubao TTS request timed out"}
        except ModuleNotFoundError:
            return {"success": False, "provider": "doubao", "error": "Missing Python dependency: websockets"}
        except Exception as exc:
            return {
                "success": False,
                "provider": "doubao",
                "error": f"Doubao TTS failed: {self._safe_error(exc)}",
            }

    @staticmethod
    def _request_params(
        *,
        text: str,
        speaker: str,
        speed_ratio: float,
        encoding: str,
        sample_rate: int,
        bit_rate: int,
        loudness_rate: int,
        enable_subtitle: bool,
        context_texts: Optional[list[str]],
        section_id: Optional[str],
        explicit_language: Optional[str],
        explicit_dialect: Optional[str],
        pitch: int,
        disable_markdown_filter: bool,
        disable_emoji_filter: bool,
        aigc_watermark: bool,
    ) -> dict[str, Any]:
        audio_params: dict[str, Any] = {
            "format": encoding,
            "sample_rate": sample_rate,
            "speech_rate": round((speed_ratio - 1.0) * 100),
            "loudness_rate": loudness_rate,
            "enable_subtitle": enable_subtitle,
        }
        if encoding == "mp3":
            audio_params["bit_rate"] = bit_rate
        additions: dict[str, Any] = {
            "disable_markdown_filter": disable_markdown_filter,
            "disable_emoji_filter": disable_emoji_filter,
        }
        if explicit_language:
            additions["explicit_language"] = explicit_language
        if explicit_dialect:
            additions["explicit_dialect"] = explicit_dialect
        params: dict[str, Any] = {
            "model": os.getenv("DOUBAO_TTS_MODEL") or DEFAULT_MODEL,
            "speaker": speaker,
            "text": text,
            "audio_params": audio_params,
            "additions": json.dumps(additions, ensure_ascii=False),
            "aigc_watermark": aigc_watermark,
            "post_process": {"pitch": pitch},
        }
        if context_texts:
            params["context_texts"] = context_texts
        if section_id:
            params["section_id"] = section_id
        return params

    async def _synthesize(
        self,
        *,
        api_key: str,
        request_params: dict[str, Any],
        destination: Path,
    ) -> dict[str, Any]:
        import websockets

        resource_id = os.getenv("DOUBAO_TTS_RESOURCE_ID") or DEFAULT_RESOURCE_ID
        ws_url = os.getenv("DOUBAO_TTS_WS_URL") or DEFAULT_WS_URL
        headers = {
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4()),
            "X-Control-Require-Usage-Tokens-Return": "*",
        }
        connect_kwargs: dict[str, Any] = {"max_size": 10 * 1024 * 1024}
        if "additional_headers" in inspect.signature(websockets.connect).parameters:
            connect_kwargs["additional_headers"] = headers
        else:
            connect_kwargs["extra_headers"] = headers

        websocket = await websockets.connect(ws_url, **connect_kwargs)
        session_id = str(uuid.uuid4())
        subtitles: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        audio_data = bytearray()
        try:
            await websocket.send(client_event(EventType.START_CONNECTION))
            await self._expect(websocket, EventType.CONNECTION_STARTED)

            start_payload = self._payload(EventType.START_SESSION, request_params, include_text=False)
            await websocket.send(client_event(EventType.START_SESSION, start_payload, session_id))
            await self._expect(websocket, EventType.SESSION_STARTED)

            task_payload = self._payload(EventType.TASK_REQUEST, request_params, include_text=True)
            await websocket.send(client_event(EventType.TASK_REQUEST, task_payload, session_id))
            await websocket.send(client_event(EventType.FINISH_SESSION, session_id=session_id))

            while True:
                raw_message = await websocket.recv()
                if not isinstance(raw_message, bytes):
                    raise RuntimeError("server returned a non-binary WebSocket frame")
                message = Message.from_bytes(raw_message)
                self._raise_for_failure(message)
                if message.message_type == MessageType.AUDIO_ONLY_SERVER and message.event == EventType.TTS_RESPONSE:
                    audio_data.extend(message.payload)
                elif message.event == EventType.TTS_SUBTITLE:
                    subtitle = self._json_payload(message.payload)
                    if subtitle:
                        subtitles.append(subtitle)
                elif message.event == EventType.SESSION_FINISHED:
                    finished = self._json_payload(message.payload)
                    usage = finished.get("usage") if isinstance(finished.get("usage"), dict) else {}
                    break

            if not audio_data:
                raise RuntimeError("server returned no audio")
            destination.write_bytes(audio_data)

            await websocket.send(client_event(EventType.FINISH_CONNECTION))
            await self._expect(websocket, EventType.CONNECTION_FINISHED)
        finally:
            await websocket.close()

        return {
            "success": True,
            "provider": "doubao",
            "model": request_params.get("model"),
            "resource_id": resource_id,
            "speaker": request_params.get("speaker"),
            "output_path": str(destination.resolve()),
            "audio_path": str(destination.resolve()),
            "format": request_params["audio_params"]["format"],
            "sample_rate": request_params["audio_params"]["sample_rate"],
            "bytes": len(audio_data),
            "usage": usage,
            "subtitles": subtitles,
        }

    @staticmethod
    def _payload(event: EventType, request_params: dict[str, Any], *, include_text: bool) -> bytes:
        params = dict(request_params)
        if not include_text:
            params.pop("text", None)
        payload = {
            "event": int(event),
            "namespace": "BidirectionalTTS",
            "user": {"uid": "capsule-cinema"},
            "req_params": params,
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    async def _expect(self, websocket: Any, expected: EventType) -> Message:
        raw_message = await websocket.recv()
        if not isinstance(raw_message, bytes):
            raise RuntimeError("server returned a non-binary WebSocket frame")
        message = Message.from_bytes(raw_message)
        self._raise_for_failure(message)
        if message.event != expected:
            raise RuntimeError(f"expected event {int(expected)}, received {int(message.event)}")
        return message

    @classmethod
    def _raise_for_failure(cls, message: Message) -> None:
        if message.message_type == MessageType.ERROR:
            detail = cls._payload_error(message.payload)
            raise RuntimeError(f"protocol error {message.error_code}: {detail}")
        if message.event in {EventType.CONNECTION_FAILED, EventType.SESSION_FAILED}:
            raise RuntimeError(cls._payload_error(message.payload))

    @staticmethod
    def _json_payload(payload: bytes) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            value = json.loads(payload.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    @classmethod
    def _payload_error(cls, payload: bytes) -> str:
        parsed = cls._json_payload(payload)
        if parsed:
            for key in ("message", "error", "error_message", "msg"):
                if parsed.get(key):
                    return str(parsed[key])[:300]
            return json.dumps(parsed, ensure_ascii=False)[:300]
        return payload.decode("utf-8", "replace")[:300] or "unknown server error"

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        api_key = os.getenv("DOUBAO_TTS_API_KEY")
        text = str(exc)
        if api_key:
            text = text.replace(api_key, "<redacted>")
        return text[:500] or exc.__class__.__name__
