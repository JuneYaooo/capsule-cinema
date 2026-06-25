"""Business production contracts for Capsule Cinema runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DELIVERY_PROMISE_SCHEMA = "capsule_cinema.delivery_promise.v1"
PRODUCTION_PROPOSAL_SCHEMA = "capsule_cinema.production_proposal.v1"
DECISION_LOG_SCHEMA = "capsule_cinema.decision_log.v1"

VALID_PROMISE_TYPES = {
    "motion_led",
    "source_led",
    "tts_led_explainer",
    "reference_remake",
    "capsule_preset",
    "specialized_route",
}

SPECIALIZED_CATEGORIES = {"action_transfer", "digital_human", "music_mv"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _safe_confidence(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.7
    return max(0.0, min(1.0, number))


def infer_promise_type(
    *,
    user_requirements: str = "",
    route: str = "",
    capsule_name: str = "",
    capsule_category: str = "",
    has_source_media: bool = False,
    has_reference_analysis: bool = False,
    has_reference_material: bool = False,
    needs_audio: bool | None = None,
    explicit: str = "",
) -> str:
    """Infer the delivery promise from route hints and user-facing inputs."""
    if explicit:
        promise_type = explicit.strip()
        if promise_type not in VALID_PROMISE_TYPES:
            raise ValueError(f"unsupported delivery promise: {promise_type}")
        return promise_type

    normalized_route = (route or "").strip().lower()
    normalized_category = (capsule_category or "").strip().lower()
    text = (user_requirements or "").lower()

    if normalized_category in SPECIALIZED_CATEGORIES or normalized_route in SPECIALIZED_CATEGORIES:
        return "specialized_route"
    if has_source_media or normalized_route in {"source", "source_edit", "post_production"}:
        return "source_led"
    if capsule_name:
        return "capsule_preset"
    if has_reference_analysis or has_reference_material or any(
        marker in text
        for marker in ("参考", "像这个", "类似这个", "remake", "reference", "like this", "in this style")
    ):
        return "reference_remake"
    if needs_audio is True or any(marker in text for marker in ("旁白", "讲解", "配音", "voiceover", "narration")):
        return "tts_led_explainer"
    return "motion_led"


def build_delivery_promise(
    *,
    user_requirements: str = "",
    route: str = "general_video",
    capsule_name: str = "",
    capsule_category: str = "",
    has_source_media: bool = False,
    has_reference_analysis: bool = False,
    has_reference_material: bool = False,
    needs_audio: bool | None = None,
    explicit: str = "",
    approved_fallback: str = "",
) -> dict[str, Any]:
    """Build a schema-stable delivery promise document."""
    promise_type = infer_promise_type(
        user_requirements=user_requirements,
        route=route,
        capsule_name=capsule_name,
        capsule_category=capsule_category,
        has_source_media=has_source_media,
        has_reference_analysis=has_reference_analysis,
        has_reference_material=has_reference_material,
        needs_audio=needs_audio,
        explicit=explicit,
    )

    qa_requirements = {
        "motion_led": [
            "Key beats must use real generated/source motion or intentional animation.",
            "Still-led fallback requires explicit approval.",
        ],
        "source_led": [
            "Source media must be inspected before planning.",
            "Source media must be materially used in final output.",
        ],
        "tts_led_explainer": [
            "TTS duration is the timing master.",
            "Final video must not freeze after audio or run silent after narration.",
        ],
        "reference_remake": [
            "Reference traits must be grounded in analysis.",
            "Output must preserve approved traits while avoiding carbon-copy imitation.",
        ],
        "capsule_preset": [
            "Capsule contract, local assets, and quality rules must be applied or migrated.",
            "Disabled capsule channels must not run blindly.",
        ],
        "specialized_route": [
            "Registered specialized tool or capsule local script must produce the final output.",
            "Generic image-to-video output is preview only unless downgrade is approved.",
        ],
    }[promise_type]

    return {
        "schema": DELIVERY_PROMISE_SCHEMA,
        "created_at": _now(),
        "promise_type": promise_type,
        "route": route,
        "capsule_name": capsule_name,
        "capsule_category": capsule_category,
        "approved_fallback": approved_fallback,
        "qa_requirements": qa_requirements,
    }


def build_production_proposal(
    *,
    user_requirements: str,
    delivery_promise: dict[str, Any],
    route: str,
    aspect_ratio: str,
    target_duration: int,
    platform: str = "",
    audio_strategy: str = "",
    tool_route: dict[str, Any] | None = None,
    risks: list[str] | None = None,
    release_bar: list[str] | None = None,
    first_scene_gate: str = "Generate and inspect one representative hard scene before batching.",
    source_review_path: str = "",
    reference_analysis_path: str = "",
) -> dict[str, Any]:
    """Build a concise run proposal artifact."""
    return {
        "schema": PRODUCTION_PROPOSAL_SCHEMA,
        "created_at": _now(),
        "route": route,
        "viewer_experience": {
            "user_requirements": user_requirements,
            "platform": platform,
            "aspect_ratio": aspect_ratio,
            "target_duration": int(target_duration),
            "audio_strategy": audio_strategy,
        },
        "delivery_promise": delivery_promise,
        "tool_route": tool_route or {},
        "risks": _clean_list(risks),
        "first_scene_gate": first_scene_gate,
        "release_bar": _clean_list(release_bar),
        "source_review_path": source_review_path,
        "reference_analysis_path": reference_analysis_path,
    }


def write_production_proposal(workspace: str | Path, proposal: dict[str, Any]) -> Path:
    workspace_path = Path(workspace).expanduser()
    output = workspace_path / "work" / "production_proposal.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def append_decision(
    workspace: str | Path,
    *,
    category: str,
    selected: str,
    options_considered: list[str] | None,
    reason: str,
    user_visible: bool = False,
    user_approved: bool | None = None,
    confidence: float = 0.7,
    qa_impact: str = "",
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Append one decision to ``work/decision_log.json``."""
    workspace_path = Path(workspace).expanduser()
    output = workspace_path / "work" / "decision_log.json"
    if output.exists():
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
    decision = {
        "id": f"d{len(decisions) + 1:03d}",
        "created_at": _now(),
        "category": category,
        "selected": selected,
        "options_considered": _clean_list(options_considered),
        "reason": reason,
        "user_visible": bool(user_visible),
        "user_approved": user_approved,
        "confidence": _safe_confidence(confidence),
        "qa_impact": qa_impact,
    }
    if metadata:
        decision["metadata"] = metadata
    decisions.append(decision)

    payload = {
        "schema": DECISION_LOG_SCHEMA,
        "run_id": workspace_path.name,
        "created_at": payload.get("created_at") or _now(),
        "updated_at": _now(),
        "decisions": decisions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def validate_preflight_contract(
    delivery_promise: dict[str, Any],
    *,
    source_review_path: str = "",
    reference_analysis_path: str = "",
    has_reference_material: bool = False,
    storyboarding_only: bool = False,
    allow_generic_fallback: bool = False,
) -> None:
    """Raise ``ValueError`` when inputs cannot satisfy an explicit promise."""
    promise_type = delivery_promise.get("promise_type", "")
    if promise_type == "source_led" and not source_review_path:
        raise ValueError("source_led delivery requires --source_review_path")
    if promise_type == "source_led" and source_review_path and not Path(source_review_path).expanduser().exists():
        raise ValueError(f"source review not found: {source_review_path}")
    if promise_type == "reference_remake" and not (
        reference_analysis_path or has_reference_material
    ):
        raise ValueError("reference_remake delivery requires reference material or --reference_analysis_path")
    if reference_analysis_path and not Path(reference_analysis_path).expanduser().exists():
        raise ValueError(f"reference analysis not found: {reference_analysis_path}")
    if promise_type == "specialized_route" and not (storyboarding_only or allow_generic_fallback):
        raise ValueError(
            "specialized_route delivery requires a specialized tool/local_script; "
            "generic run_video.py may only be used for storyboard/preview"
        )
