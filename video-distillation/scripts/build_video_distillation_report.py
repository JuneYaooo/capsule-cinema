#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


RouteValue = bool | str

CTA_TERMS = [
    "comment",
    "follow",
    "save",
    "share",
    "dm",
    "\u8bc4\u8bba",
    "\u5173\u6ce8",
    "\u9886\u53d6",
    "\u79c1\u4fe1",
    "\u6536\u85cf",
    "\u8f6c\u53d1",
]
CONTRAST_TERMS = ["not", "but", "instead", "\u4e0d\u662f", "\u800c\u662f", "\u4f46\u662f", "\u5374"]
IDENTITY_TERMS = ["you", "beginner", "ordinary person", "\u4f60", "\u666e\u901a\u4eba", "\u65b0\u624b"]
RISK_TERMS = ["risk", "wrong", "mistake", "skip", "\u522b", "\u4e0d\u8981", "\u98ce\u9669", "\u9519", "\u5212\u8d70"]
PROOF_TERMS = [
    "proof",
    "result",
    "tested",
    "case",
    "watch",
    "\u8bc1\u660e",
    "\u7ed3\u679c",
    "\u5b9e\u6d4b",
    "\u6848\u4f8b",
    "\u770b",
]

TRANSCRIPT_VALUE_KEYS = {
    "copy_evidence",
    "exact_observed_text",
    "spoken_opening",
    "transcript",
    "transcript_evidence",
    "transcript_snippet",
    "transcript_snippets",
    "visible_opening",
}
SENSITIVE_KEY_PARTS = (
    "account",
    "account_id",
    "api_key",
    "authorization",
    "author",
    "avatar",
    "cookie",
    "display_name",
    "header",
    "handle",
    "nickname",
    "play_url",
    "profile",
    "secret",
    "sec_uid",
    "signed",
    "screen_name",
    "source_copy",
    "source_url",
    "token",
    "uid",
    "unique_id",
    "url",
    "user_id",
    "username",
    "watermark",
)

URL_PATTERN = re.compile(r"https?://|x-amz-signature|signature=", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"\b(?:api[_-]?key|authorization|bearer|cookie|sessionid|secret|sk-[a-z0-9]|token)\b",
    re.IGNORECASE,
)
FRAME_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:03_keyframes/)?(?:frames/)?[^/\s]*(?:frame|keyframe)[^/\s]*\."
    r"(?:jpg|jpeg|png|webp)\b|03_keyframes/",
    re.IGNORECASE,
)
TRANSCRIPT_MARKER_PATTERN = re.compile(r"\b(?:transcript|snippet|quote|caption)\s*[:\uff1a]", re.IGNORECASE)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).strip()
    return str(value).strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _first_sentence(text: str, fallback: str = "") -> str:
    cleaned = _compact(text)
    if not cleaned:
        return _compact(fallback)
    parts = re.split(r"[\u3002\uff01\uff1f.!?]\s*", cleaned, maxsplit=1)
    return parts[0].strip() or _compact(fallback)


def _sentences(text: str) -> list[str]:
    cleaned = _compact(text)
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"[\u3002\uff01\uff1f.!?]\s*", cleaned) if item.strip()]


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = _compact(text).lower()
    return any(needle.lower() in lowered for needle in needles)


def _format_seconds(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:g}s"
    raw = _text(value)
    if not raw:
        return ""
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return f"{float(raw):g}s"
    return raw


def _timestamp_value(item: dict[str, Any]) -> str:
    for key in ("timestamp", "timecode", "time"):
        if key in item and item[key] is not None:
            return _format_seconds(item[key])
    return ""


def _time_range(start: Any, end: Any) -> str:
    return f"{_format_seconds(start) or '0s'}-{_format_seconds(end) or '3s'}"


def _media_ref(media_info: dict[str, Any], key: str) -> str:
    if key in media_info and media_info[key] is not None:
        return f"media_info.{key}={media_info[key]}"
    return f"inference: media_info.{key} unavailable"


def _transcript_evidence(snippet: str, time_range: str = "0:00-0:03") -> str:
    cleaned = _first_sentence(snippet)
    if cleaned:
        return f"{time_range} transcript: {cleaned}"
    return f"{time_range} inference: transcript snippet unavailable"


def _keyframe_evidence(keyframes: list[dict[str, Any]], limit: int = 3) -> list[str]:
    evidence: list[str] = []
    for item in keyframes[:limit]:
        path = _text(
            item.get("path")
            or item.get("frame_path")
            or item.get("keyframe_path")
            or item.get("file")
        )
        timestamp = _timestamp_value(item)
        label = _text(item.get("label") or item.get("visible_text"))
        parts: list[str] = []
        if path:
            parts.append(path)
        if timestamp:
            parts.append(f"timestamp={timestamp}")
        if label:
            parts.append(f"label={label}")
        if path or timestamp:
            evidence.append(" ".join(parts))
    return evidence or ["inference: no keyframes supplied to this builder"]


def _extract_hashtags(*values: str) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for value in values:
        for tag in re.findall(r"#([^\s#]+)", value):
            if tag not in seen:
                seen.add(tag)
                tags.append(tag)
    return tags


def _observed_cta_sentence(transcript: str) -> str:
    for sentence in reversed(_sentences(transcript)):
        if _contains_any(sentence, CTA_TERMS):
            return sentence
    return ""


def _default_copy_beats(transcript: str) -> list[dict[str, Any]]:
    sentences = _sentences(transcript)
    opening = sentences[0] if sentences else ""
    middle = " ".join(sentences[1:-1]) if len(sentences) > 2 else (sentences[1] if len(sentences) > 1 else "")
    ending = sentences[-1] if len(sentences) > 1 else ""
    return [
        {
            "time_range": "0:00-0:03",
            "role": "hook",
            "transcript_evidence": opening,
            "retention_function": "establishes the viewer question or stop reason",
        },
        {
            "time_range": "0:03-0:09",
            "role": "proof_or_development",
            "transcript_evidence": middle,
            "retention_function": "keeps the opening promise alive with proof or development",
        },
        {
            "time_range": "0:09-0:12",
            "role": "payoff_or_cta",
            "transcript_evidence": ending,
            "retention_function": "closes the promise or asks for the next action",
        },
    ]


def _normalize_copy_beats(beats: list[dict[str, Any]], transcript: str) -> list[dict[str, Any]]:
    source_beats = beats or _default_copy_beats(transcript)
    normalized: list[dict[str, Any]] = []
    for index, beat in enumerate(source_beats):
        time_range = _text(beat.get("time_range")) or _time_range(index * 3, (index + 1) * 3)
        snippet = _text(
            beat.get("transcript_evidence")
            or beat.get("copy_evidence")
            or beat.get("transcript_snippet")
        )
        visual_evidence = _text(beat.get("visual_evidence"))
        evidence = [
            _transcript_evidence(snippet, time_range),
            visual_evidence or f"{time_range} inference: visual evidence not supplied to copy builder",
        ]
        normalized.append(
            {
                "time_range": time_range,
                "role": _text(beat.get("role")) or f"beat_{index + 1}",
                "transcript_evidence": snippet,
                "visual_evidence": visual_evidence,
                "retention_function": _text(beat.get("retention_function"))
                or "supports the promise-proof-payoff sequence",
                "evidence": evidence,
            }
        )
    return normalized


def _abstract_script_template() -> str:
    return (
        "Open with a concrete result, error, conflict, or promise; name the viewer problem; "
        "develop proof through demo, story, comparison, or explanation; then close with a "
        "payoff or next action. Do not reuse the source wording."
    )


def build_copy_logic(
    source: dict[str, Any],
    transcript: str,
    beats: list[dict[str, Any]],
    evidence_level: str,
) -> dict[str, Any]:
    title = _text(source.get("title") or source.get("caption"))
    caption = _text(source.get("caption"))
    opening = _first_sentence(transcript, title)
    cta_observed = _observed_cta_sentence(transcript)
    all_copy_text = f"{title} {caption} {transcript}"
    numbers = re.findall(r"\d+(?:\.\d+)?", all_copy_text)

    return {
        "schema_version": "capsule_cinema.video_copy_logic.v1",
        "evidence_level": evidence_level,
        "source_copy": {
            "title": title,
            "caption": caption,
            "hashtags": _extract_hashtags(title, caption),
        },
        "hook": {
            "exact_observed_text": opening,
            "spoken_opening": opening if transcript else "",
            "visible_opening": _text(source.get("visible_opening")),
            "mechanism": "direct_problem_result_or_conflict_first",
            "viewer_pressure": "viewer receives a concrete reason to keep watching before background",
            "curiosity_gap": "the opening raises why the problem happens or how the promised result resolves",
            "evidence": [
                _transcript_evidence(opening, "0:00-0:03"),
                "inference: hook mechanism inferred from the first observed copy beat",
            ],
        },
        "promise": {
            "what_viewer_expects": title or opening,
            "when_promise_is_opened": "0:00-0:03",
            "when_promise_is_paid_off": "ending_or_main_proof",
            "evidence": [
                _transcript_evidence(opening, "0:00-0:03"),
                "ending inference: payoff timing should be verified against final transcript or frame evidence",
            ],
        },
        "script_structure": {
            "beats": _normalize_copy_beats(beats, transcript),
            "evidence": [
                _transcript_evidence(opening, "0:00-0:03"),
                "inference: supplied beat list normalized into copy roles",
            ],
        },
        "copy_devices": {
            "specificity": "observed" if numbers else "limited",
            "contrast": "observed" if _contains_any(all_copy_text, CONTRAST_TERMS) else "limited",
            "numbers": numbers,
            "identity_address": "observed" if _contains_any(transcript, IDENTITY_TERMS) else "limited",
            "risk_or_loss": "observed" if _contains_any(transcript, RISK_TERMS) else "limited",
            "proof_language": "observed" if _contains_any(transcript, PROOF_TERMS) else "limited",
            "evidence": [
                _transcript_evidence(opening, "0:00-0:03"),
                "inference: copy devices detected by deterministic lexical rules",
            ],
        },
        "cta": {
            "observed": cta_observed,
            "type": "comment_follow_save_or_share" if cta_observed else "not_observed",
            "timing": "ending" if cta_observed else "",
            "comment_driver": cta_observed,
            "evidence": [
                f"ending transcript: {cta_observed}"
                if cta_observed
                else "inference: no CTA language found in supplied transcript"
            ],
        },
        "rewrite_template": {
            "reusable_hook_formula": (
                "Start with the result, mistake, conflict, or verifiable promise before any background."
            ),
            "reusable_script_template": _abstract_script_template(),
            "forbidden_to_copy": [
                "source title",
                "source transcript",
                "source account identity",
                "source frames",
                "signed media URLs",
            ],
            "evidence": [
                "inference: template abstracts the observed copy structure without copying source wording",
            ],
        },
        "confidence": {
            "transcript_completeness": "present" if transcript else "missing",
            "unsupported_claims": [],
            "evidence": [
                _transcript_evidence(opening, "0:00-0:03") if transcript else "inference: transcript missing",
            ],
        },
    }


def _timeline_ranges(keyframes: list[dict[str, Any]]) -> tuple[str, str, str]:
    timestamps: list[Any] = [
        item.get("timestamp")
        for item in keyframes
        if isinstance(item.get("timestamp"), (int, float))
    ]
    if len(timestamps) >= 3:
        return (
            _time_range(timestamps[0], timestamps[1]),
            _time_range(timestamps[1], timestamps[-1]),
            _time_range(max(float(timestamps[-1]) - 3.0, 0.0), timestamps[-1]),
        )
    if len(timestamps) == 2:
        return (
            _time_range(timestamps[0], timestamps[1]),
            _time_range(timestamps[1], float(timestamps[1]) + 6.0),
            _time_range(float(timestamps[1]) + 6.0, float(timestamps[1]) + 9.0),
        )
    return ("0:00-0:03", "0:03-0:09", "0:09-0:12")


def build_beat_timeline(
    transcript: str,
    keyframes: list[dict[str, Any]],
    gemini: dict[str, Any] | None,
) -> dict[str, Any]:
    gemini = gemini or {}
    sentences = _sentences(transcript)
    opening = sentences[0] if sentences else _text(gemini.get("opening")) or "opening unavailable"
    middle = " ".join(sentences[1:-1]) if len(sentences) > 2 else (sentences[1] if len(sentences) > 1 else "")
    ending = sentences[-1] if len(sentences) > 1 else _text(gemini.get("ending"))
    hook_range, proof_range, ending_range = _timeline_ranges(keyframes)
    first_frame_evidence = _keyframe_evidence(keyframes[:1])
    middle_frame_evidence = _keyframe_evidence(keyframes[1:-1] or keyframes[:2])
    ending_frame_evidence = _keyframe_evidence(keyframes[-1:] if keyframes else [])

    beats = [
        {
            "time_range": hook_range,
            "role": "hook",
            "copy_evidence": opening,
            "visual_evidence": first_frame_evidence,
            "audio_evidence": _transcript_evidence(opening, hook_range) if transcript else "inference: no transcript supplied",
            "retention_function": "opens the viewer question and gives a reason to stop scrolling",
            "implementation_dependency": "opening copy plus first-frame visual proof",
            "evidence": [_transcript_evidence(opening, hook_range), *first_frame_evidence],
        },
        {
            "time_range": proof_range,
            "role": "proof_or_development",
            "copy_evidence": middle or _text(gemini.get("proof")) or "inference: proof beat inferred from structure",
            "visual_evidence": middle_frame_evidence,
            "audio_evidence": _transcript_evidence(middle or opening, proof_range)
            if transcript
            else "inference: proof narration unavailable",
            "retention_function": "keeps the promise alive with proof, demo, story, or explanation",
            "implementation_dependency": "clear sequence of evidence beats",
            "evidence": [_transcript_evidence(middle or opening, proof_range), *middle_frame_evidence],
        },
        {
            "time_range": ending_range,
            "role": "ending_or_cta",
            "copy_evidence": ending or "inference: ending requires payoff or CTA verification",
            "visual_evidence": ending_frame_evidence,
            "audio_evidence": _transcript_evidence(ending or opening, ending_range)
            if transcript
            else "inference: ending narration unavailable",
            "retention_function": "closes the viewer question or drives the next action",
            "implementation_dependency": "payoff or CTA must match the opening promise",
            "evidence": [_transcript_evidence(ending or opening, ending_range), *ending_frame_evidence],
        },
    ]

    return {
        "schema_version": "capsule_cinema.video_beat_timeline.v1",
        "beats": beats,
        "logic_summary": {
            "core_loop": "inference: open a concrete viewer question, delay closure with proof, close with payoff or CTA",
            "viewer_question_opened": _transcript_evidence(opening, hook_range),
            "viewer_question_closed": _transcript_evidence(ending or opening, ending_range),
            "main_retention_device": _text(gemini.get("main_retention_device"))
            or "inference: promise-proof-payoff loop",
            "weak_points": [],
            "evidence": [
                _transcript_evidence(opening, hook_range),
                _transcript_evidence(ending or opening, ending_range),
                *_keyframe_evidence(keyframes),
            ],
        },
    }


def _route_item(value: RouteValue, reason: str, evidence: list[str]) -> dict[str, Any]:
    concrete_evidence = [item for item in evidence if _text(item)]
    if not concrete_evidence:
        concrete_evidence = ["inference: route decision made without direct media evidence"]
    return {"value": value, "reason": reason, "evidence": concrete_evidence}


def _infer_visual_medium(gemini: dict[str, Any], keyframes: list[dict[str, Any]], copy_logic: dict[str, Any]) -> str:
    supplied = _text(gemini.get("visual_medium") or gemini.get("medium"))
    if supplied:
        return supplied
    text = " ".join(
        [
            _text(item.get("visible_text") or item.get("label") or item.get("path"))
            for item in keyframes
        ]
    )
    text += " " + json.dumps(copy_logic, ensure_ascii=False, default=str)
    if _contains_any(text, ["card", "slide", "text", "\u5361\u7247", "\u5b57\u5e55"]):
        return "text_card_or_subtitle_explainer"
    if _contains_any(text, ["screen", "ui", "web", "app", "\u5c4f\u5f55", "\u7f51\u9875"]):
        return "screen_recording_or_ui_demo"
    if _contains_any(text, ["talking head", "digital human", "\u53e3\u64ad", "\u6570\u5b57\u4eba"]):
        return "talking_head_or_digital_human"
    return "unknown_or_hybrid"


def build_production_logic(
    media_info: dict[str, Any],
    keyframes: list[dict[str, Any]],
    gemini: dict[str, Any] | None,
    copy_logic: dict[str, Any],
) -> dict[str, Any]:
    gemini = gemini or {}
    visual_medium = _infer_visual_medium(gemini, keyframes, copy_logic)
    keyframe_text = " ".join(
        _text(item.get("visible_text") or item.get("label") or item.get("path")) for item in keyframes
    )
    modality_text = f"{visual_medium} {keyframe_text} {json.dumps(copy_logic, ensure_ascii=False, default=str)}"
    card_like = _contains_any(modality_text, ["card", "slide", "text_card", "\u5361\u7247", "\u5b57\u5e55"])
    screen_like = _contains_any(modality_text, ["screen", "ui", "github", "web", "\u5c4f\u5f55", "\u7f51\u9875"])
    digital_human_like = _contains_any(
        modality_text, ["digital human", "talking head", "presenter", "\u6570\u5b57\u4eba", "\u53e3\u64ad"]
    )
    ai_story_like = _contains_any(
        modality_text, ["ai animation", "ai_story", "storyboard", "anime", "\u52a8\u6f2b", "\u5206\u955c"]
    )
    has_audio = bool(media_info.get("has_audio"))
    keyframe_refs = _keyframe_evidence(keyframes)
    media_evidence = [
        _media_ref(media_info, "duration_seconds"),
        _media_ref(media_info, "width"),
        _media_ref(media_info, "height"),
        _media_ref(media_info, "aspect_ratio"),
        _media_ref(media_info, "has_audio"),
    ]
    medium_evidence = [f"inference: visual_medium={visual_medium}", *keyframe_refs]
    motion_evidence = [
        f"inference: gemini.motion={_text(gemini.get('motion')) or 'not_supplied'}",
        *keyframe_refs[:2],
    ]
    audio_evidence = [
        _media_ref(media_info, "has_audio"),
        f"inference: gemini.audio={_text(gemini.get('audio')) or 'not_supplied'}",
    ]

    route = {
        "needs_ai_image_generation": _route_item(
            ai_story_like,
            "Use generated stills when the observed medium is an AI/storyboard scene format.",
            medium_evidence if ai_story_like else ["inference: no AI-story visual markers in keyframes or Gemini medium"],
        ),
        "needs_ai_video_generation": _route_item(
            ai_story_like,
            "Use image-to-video or text-to-video only when scene motion is part of the format.",
            motion_evidence if ai_story_like else ["inference: no AI-video scene-motion requirement observed"],
        ),
        "needs_digital_human": _route_item(
            digital_human_like,
            "Talking-head or presenter formats can be reproduced with a new presenter or digital human.",
            medium_evidence
            if digital_human_like
            else ["inference: no talking-head or digital-human marker observed"],
        ),
        "needs_tts": _route_item(
            True,
            "Transcript-backed copy logic needs a repeatable narration track unless replaced by a new human voice.",
            ["0:00-0:03 transcript: copy logic contains a spoken or subtitle-led opening"],
        ),
        "needs_original_voiceover": _route_item(
            False,
            "Original voice should not be reused; use TTS or a newly recorded voice unless the project has rights.",
            ["inference: source-identity voice is not required for the reusable route"],
        ),
        "needs_screen_recording": _route_item(
            screen_like,
            "Screen or UI evidence must be recreated with fresh recordings or mock footage.",
            medium_evidence if screen_like else ["inference: no screen/UI marker observed in keyframes or Gemini medium"],
        ),
        "needs_local_card_rendering": _route_item(
            card_like,
            "Text-card formats need deterministic local rendering for titles, subtitles, and proof cards.",
            medium_evidence if card_like else ["inference: no card/subtitle-led visual marker observed"],
        ),
        "needs_motion_graphics": _route_item(
            card_like or screen_like or bool(gemini.get("motion")),
            "Cards, UI zooms, subtitles, arrows, and proof emphasis need simple motion graphics.",
            motion_evidence,
        ),
        "needs_subtitle_burn_in": _route_item(
            True,
            "Short-form retention should preserve readable on-screen copy unless the format is purely visual.",
            ["inference: subtitle burn-in recommended from transcript-backed short-form structure"],
        ),
        "needs_bgm": _route_item(
            has_audio,
            "Use safe low-volume BGM when the original has audio pacing; omit when silent logic is enough.",
            [_media_ref(media_info, "has_audio")],
        ),
        "needs_sfx": _route_item(
            "optional",
            "Use SFX only for transitions, proof moments, or UI emphasis.",
            ["inference: no mandatory SFX marker observed; optional emphasis only"],
        ),
        "needs_manual_editing": _route_item(
            True,
            "Final timing, subtitles, audio mix, and QA need manual editing even with generated assets.",
            [_media_ref(media_info, "duration_seconds"), "inference: release assembly requires edit QA"],
        ),
    }

    return {
        "schema_version": "capsule_cinema.video_production_logic.v1",
        "evidence_level": "V5_production_logic_distilled",
        "visual_style": {
            "medium": visual_medium,
            "aspect_ratio": media_info.get("aspect_ratio")
            or f"{media_info.get('width', '')}x{media_info.get('height', '')}".strip("x"),
            "frame_grammar": "observed_from_keyframes" if keyframes else "limited_without_keyframes",
            "typography": "text_or_card_driven" if card_like else "not_primary_or_unverified",
            "palette": _text(gemini.get("palette")) or "inference: palette requires keyframe or Gemini review",
            "evidence": [*media_evidence, *medium_evidence],
        },
        "motion_and_editing": {
            "motion_patterns": gemini.get("motion") or [],
            "edit_rhythm": _text(gemini.get("edit_rhythm"))
            or "inference: rhythm inferred from keyframe spacing and short-form structure",
            "subtitle_motion": "required_if_subtitles_drive_retention",
            "evidence": motion_evidence,
        },
        "audio_logic": {
            "has_audio": has_audio,
            "voice_or_tts": "tts_viable" if copy_logic else "unknown",
            "bgm_role": "pace_support" if has_audio else "not_observed",
            "sfx_role": "optional_emphasis",
            "evidence": audio_evidence,
        },
        "production_route": route,
        "cheapest_viable_route": (
            "inference: cheapest viable route from media_info.has_audio and keyframe modality is "
            "TTS/new voice + deterministic cards/subtitles + simple motion graphics + ffmpeg assembly"
        ),
        "highest_fidelity_route": (
            "inference: highest fidelity route recreates the observed medium with fresh generated or recorded "
            "visuals, timed narration, BGM/SFX, and manual edit QA"
        ),
        "recommended_route": (
            "inference: choose the cheapest route that preserves the hook, proof, visual grammar, and "
            "audio timing shown by media_info and keyframe evidence"
        ),
        "required_materials": [
            "script rewrite",
            "fresh visual evidence plan",
            "new voice or TTS",
            "subtitles",
            "licensed or generated BGM if audio-led",
        ],
        "replaceable_materials": [
            "source account identity",
            "source frames",
            "source exact script",
            "signed media URLs",
        ],
        "hardest_part_to_reproduce": (
            "inference: the hardest part is preserving the first-three-second stop reason and proof alignment"
        ),
        "quality_risks": [
            "generic visuals",
            "copied wording",
            "weak opening proof",
            "subtitle overcrowding",
        ],
        "do_not_copy": [
            "source logo",
            "source watermark",
            "source handle",
            "source exact script",
            "source frames",
        ],
    }


def _scalar_fragments(value: Any) -> list[str]:
    text = _compact(value)
    if not text:
        return []
    fragments = [text]
    fragments.extend(sentence for sentence in _sentences(text) if len(sentence) >= 2)
    return fragments


def _collect_forbidden_fragments(value: Any, path: tuple[str, ...] = ()) -> set[str]:
    fragments: set[str] = set()
    key = path[-1].lower() if path else ""
    sensitive_path = any(any(part in item.lower() for part in SENSITIVE_KEY_PARTS) for item in path)
    transcript_path = key in TRANSCRIPT_VALUE_KEYS

    if isinstance(value, dict):
        for child_key, child_value in value.items():
            fragments.update(_collect_forbidden_fragments(child_value, (*path, str(child_key))))
        return fragments
    if isinstance(value, (list, tuple, set)):
        for item in value:
            fragments.update(_collect_forbidden_fragments(item, path))
        return fragments

    text = _compact(value)
    if not text:
        return fragments
    if (
        sensitive_path
        or transcript_path
        or TRANSCRIPT_MARKER_PATTERN.search(text)
        or URL_PATTERN.search(text)
        or SECRET_PATTERN.search(text)
    ):
        fragments.update(_scalar_fragments(text))
    return fragments


def _recipe_safe_string(text: str, forbidden_fragments: set[str]) -> str:
    value = _compact(text)
    if not value:
        return ""
    lowered = value.lower()
    for fragment in forbidden_fragments:
        if fragment and (fragment in value or fragment.lower() in lowered):
            return "inference: source-derived detail removed from reusable recipe seed"
    if URL_PATTERN.search(value):
        return "inference: URL removed from reusable recipe seed"
    if SECRET_PATTERN.search(value):
        return "inference: secret or credential-like value removed from reusable recipe seed"
    if FRAME_PATH_PATTERN.search(value):
        return "inference: source-frame evidence abstracted into route decision"
    if TRANSCRIPT_MARKER_PATTERN.search(value):
        return "inference: copied transcript wording removed from reusable recipe seed"
    return value


def _recipe_safe(value: Any, forbidden_fragments: set[str]) -> Any:
    if isinstance(value, dict):
        return {key: _recipe_safe(item, forbidden_fragments) for key, item in value.items()}
    if isinstance(value, list):
        return [_recipe_safe(item, forbidden_fragments) for item in value]
    if isinstance(value, tuple):
        return [_recipe_safe(item, forbidden_fragments) for item in value]
    if isinstance(value, str):
        return _recipe_safe_string(value, forbidden_fragments)
    return value


def _route_for_recipe(production_route: dict[str, Any], forbidden_fragments: set[str]) -> dict[str, Any]:
    safe_route: dict[str, Any] = {}
    for key, item in production_route.items():
        if not isinstance(item, dict):
            safe_route[key] = {
                "value": _recipe_safe(item, forbidden_fragments),
                "reason": "inference: route value carried from sanitized production logic",
                "evidence": ["inference: source evidence omitted from recipe seed"],
            }
            continue
        safe_route[key] = {
            "value": _recipe_safe(item.get("value"), forbidden_fragments),
            "reason": _recipe_safe_string(
                _text(item.get("reason")) or "inference: route reason carried from production logic",
                forbidden_fragments,
            ),
            "evidence": ["inference: source media evidence omitted from reusable recipe seed"],
        }
    return safe_route


def build_recipe_seed(
    copy_logic: dict[str, Any],
    beat_timeline: dict[str, Any],
    production_logic: dict[str, Any],
) -> dict[str, Any]:
    forbidden_fragments: set[str] = set()
    for value in (copy_logic, beat_timeline, production_logic):
        forbidden_fragments.update(_collect_forbidden_fragments(value))

    rewrite_template = copy_logic.get("rewrite_template") if isinstance(copy_logic, dict) else {}
    if not isinstance(rewrite_template, dict):
        rewrite_template = {}
    logic_summary = beat_timeline.get("logic_summary") if isinstance(beat_timeline, dict) else {}
    if not isinstance(logic_summary, dict):
        logic_summary = {}
    production_route = production_logic.get("production_route") if isinstance(production_logic, dict) else {}
    if not isinstance(production_route, dict):
        production_route = {}

    seed = {
        "schema_version": "capsule_cinema.video_distillation_recipe_seed.v1",
        "source_safety": {
            "source_identity_forbidden": True,
            "copy_source_script_forbidden": True,
            "source_frames_forbidden": True,
            "signed_urls_forbidden": True,
            "secrets_headers_cookies_forbidden": True,
        },
        "copy_formula": {
            "hook_formula": _recipe_safe_string(
                _text(rewrite_template.get("reusable_hook_formula"))
                or "Start with a concrete result, mistake, conflict, or verifiable promise.",
                forbidden_fragments,
            ),
            "script_template": _recipe_safe_string(
                _text(rewrite_template.get("reusable_script_template")) or _abstract_script_template(),
                forbidden_fragments,
            ),
        },
        "video_logic": {
            "core_loop": _recipe_safe_string(
                _text(logic_summary.get("core_loop"))
                or "Open a viewer question, sustain proof, close with payoff or CTA.",
                forbidden_fragments,
            ),
            "viewer_question_formula": (
                "Open a concrete question in the first three seconds, develop proof, then close the loop."
            ),
            "main_retention_device": _recipe_safe_string(
                _text(logic_summary.get("main_retention_device")) or "promise-proof-payoff loop",
                forbidden_fragments,
            ),
        },
        "production_route": _route_for_recipe(production_route, forbidden_fragments),
        "recommended_route": _recipe_safe_string(
            _text(production_logic.get("recommended_route"))
            or "Use the cheapest fresh-material route that preserves hook, proof, pacing, and readability.",
            forbidden_fragments,
        ),
        "quality_gates": [
            "first_three_seconds_stop_reason",
            "promise_proof_payoff_alignment",
            "no_source_identity",
            "no_copied_script",
            "no_signed_urls_or_credentials",
            "subtitle_readability",
            "route_matches_visual_medium",
        ],
    }
    return _recipe_safe(seed, forbidden_fragments)


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_yaml(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return path
