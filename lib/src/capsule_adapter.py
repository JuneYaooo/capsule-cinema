"""Output-contract adapter (L5).

Capability-driven reconciliation: given a capsule's Output Contract and the
selected tool's declared capability (``provides``), produce the concrete
execution directive (prompt injections + post-processing steps) so the fixed
pipeline always converges to the contract regardless of which tool was chosen.

Audio directives are executable in the current runtime. On-frame text is
validated here, but blocked until image-prompt injection or overlay rendering is
wired into the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_SILENCE_NEGATIVES = ["no speech", "no dialogue", "no singing"]


@dataclass
class ExecutionDirective:
    prompt_additions: list[str] = field(default_factory=list)
    prompt_negatives: list[str] = field(default_factory=list)
    post_steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


def _flags(provides: dict) -> dict:
    return provides.get("flags", {})


def _enums(provides: dict) -> dict:
    return provides.get("enums", {})


def _reconcile_audio(contract: dict, provides: dict, directive: ExecutionDirective) -> None:
    clip_audio = contract.get("clip_audio")
    native_audio = _flags(provides).get("native_audio") is True
    if clip_audio == "native" and not native_audio:
        directive.blocked.append("native_audio")
    if clip_audio == "sfx_only":
        if not native_audio:
            directive.blocked.append("native_audio")
        directive.blocked.append("strip_voice_post_processor")
        directive.notes.append("clip_audio=sfx_only 需要人声分离后处理；当前运行时未接入该能力")
        return
    if clip_audio == "silent" and native_audio:
        directive.prompt_negatives.extend(_SILENCE_NEGATIVES)
        directive.post_steps.append("mute_audio")
        directive.notes.append(
            f"引擎原生有声，按契约 clip_audio={clip_audio} 注入负向提示并后期处理"
        )


def _reconcile_on_frame_text(contract: dict, provides: dict, directive: ExecutionDirective) -> None:
    if contract.get("on_frame_text") != "required":
        return
    rendering = _enums(provides).get("text_rendering")
    if rendering == "reliable":
        directive.blocked.append("on_frame_text_runtime")
        directive.notes.append("on_frame_text=required 需要图片生成运行时消费文字指令；当前尚未接线")
        return
    if contract.get("on_frame_text_fallback") == "overlay":
        directive.blocked.append("overlay_text_runtime")
        directive.notes.append("on_frame_text overlay fallback 需要明确文字源和后期叠加实现；当前尚未接线")
        return
    directive.blocked.append("on_frame_text")
    directive.notes.append("on_frame_text=required 但工具文字渲染不可靠，且胶囊未授权 overlay fallback")


def reconcile(contract: dict, provides: dict) -> ExecutionDirective:
    directive = ExecutionDirective()
    _reconcile_audio(contract, provides, directive)
    _reconcile_on_frame_text(contract, provides, directive)
    return directive
