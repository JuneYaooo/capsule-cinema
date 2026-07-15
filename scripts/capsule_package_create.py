#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from capsule_package_validate import validate_capsule_dir

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from src.capsule_copywriting_contract import (  # noqa: E402
    COPY_RECIPE_DEFAULT_BODY,
    STRUCTURE_RECIPE_DEFAULT_BODY,
    default_copywriting_structure_contract,
)
from src.capsule_content_scope import default_content_scope_contract  # noqa: E402
from src.capsule_script_policy import (  # noqa: E402
    CapsuleScriptPolicyError,
    load_script_evidence,
    normalize_script_evidence,
)


VIDEO_OKF_PROFILE = "video.okf.capsule.v1"
OKF_VERSION = "0.1"
SAFE_CAPSULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
ALLOWED_EXECUTION_MODES = {"preset", "local_script"}
TRANSIENT_SCRIPT_NAMES = {".DS_Store", "__pycache__"}

DEFAULT_READ_ORDER = {
    "routing": ["index.md", "CARD.md", "contracts/input_schema.yaml", "contracts/content_scope.yaml"],
    "planning": [
        "contracts/input_schema.yaml",
        "contracts/content_scope.yaml",
        "contracts/production_contract.yaml",
        "recipes/structure.md",
        "recipes/copy.md",
        "recipes/visual.md",
        "recipes/audio.md",
    ],
    "generation": ["contracts/runtime.yaml", "recipes/motion.md", "assets/index.yaml"],
    "qa": ["quality/rules.yaml", "quality/release_gates.yaml"],
    "learning": ["learning/promoted_lessons.yaml"],
}

RECIPE_META = {
    "structure": {
        "title": "Structure Recipe",
        "description": "Story structure, pacing, beats, and scene architecture.",
        "stage": "planning",
        "empty_rule": "No capsule-specific structure rules. Use the global video production policy for story, pacing, and scene planning.",
    },
    "copy": {
        "title": "Copy Recipe",
        "description": "Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.",
        "stage": "planning",
        "empty_rule": "No capsule-specific copy rules. Use the global video production policy for voiceover, subtitles, titles, and packaging copy.",
    },
    "visual": {
        "title": "Visual Recipe",
        "description": "Visual style, references, characters, scenes, composition, and continuity.",
        "stage": "planning",
        "empty_rule": "No capsule-specific visual rules. Use the global video production policy for style, references, scene design, and continuity.",
    },
    "audio": {
        "title": "Audio Recipe",
        "description": "TTS, original audio, BGM, SFX, mix, timing, and sync rules.",
        "stage": "planning",
        "empty_rule": "No capsule-specific audio rules. Use the global video production policy for TTS, original audio, BGM, SFX, mix, and sync.",
    },
    "motion": {
        "title": "Motion Recipe",
        "description": "Camera motion, action, transitions, dynamic generation, and editing rhythm.",
        "stage": "generation",
        "empty_rule": "No capsule-specific motion rules. Use the global video production policy for camera motion, transitions, dynamic generation, and editing rhythm.",
    },
}


def _dedupe(values: list[str] | tuple[str, ...] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def _dump_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _frontmatter(meta: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).strip() + "\n---\n\n" + body.strip() + "\n"


def _validate_capsule_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise SystemExit("capsule name is required")
    if not SAFE_CAPSULE_NAME.fullmatch(normalized):
        raise SystemExit(f"capsule name must be a safe slug: {normalized!r}")
    return normalized


def _validate_local_script_source(
    source_value: str | Path,
    *,
    local_script_entry: str = "",
) -> tuple[Path, str]:
    source_path = Path(source_value).expanduser()
    if source_path.is_symlink():
        raise SystemExit(f"local_script source must not be a symlink: {source_path}")
    source = source_path.resolve()
    if not source.exists():
        raise SystemExit(f"local_script source missing: {source_value}")
    if source.is_file():
        if source.suffix.lower() != ".py":
            raise SystemExit("local_script source file must be a Python file")
        if local_script_entry and Path(local_script_entry).name != source.name:
            raise SystemExit("local_script_entry must match the source filename for a single-file script")
        return source, source.name
    if not source.is_dir():
        raise SystemExit(f"local_script source must be a file or directory: {source}")

    entry_text = str(local_script_entry or "").strip()
    if not entry_text:
        raise SystemExit("local_script_entry is required when local_script source is a directory")
    entry = Path(entry_text)
    if entry.is_absolute() or ".." in entry.parts:
        raise SystemExit(f"unsafe local_script_entry: {entry_text}")
    entry_source = (source / entry).resolve()
    if not entry_source.is_relative_to(source) or not entry_source.is_file():
        raise SystemExit(f"local_script_entry not found in source directory: {entry_text}")
    if entry_source.suffix.lower() != ".py":
        raise SystemExit("local_script_entry must be a Python file")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise SystemExit(f"local_script bundle must not contain symlinks: {path}")
        if path.name in TRANSIENT_SCRIPT_NAMES or path.suffix.lower() == ".pyc":
            raise SystemExit(f"local_script bundle contains transient file: {path}")
    return source, entry.as_posix()


def install_local_script_bundle(
    capsule_dir: str | Path,
    source_value: str | Path,
    *,
    local_script_entry: str = "",
    replace: bool = False,
) -> str:
    root = Path(capsule_dir).expanduser().resolve()
    source, entry = _validate_local_script_source(
        source_value,
        local_script_entry=local_script_entry,
    )
    if source == root or source.is_relative_to(root):
        raise SystemExit("local_script source must be outside the target capsule package")
    scripts_dir = root / "scripts"
    if scripts_dir.exists():
        if not replace:
            raise SystemExit(f"capsule scripts directory already exists: {scripts_dir}")
        shutil.rmtree(scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copy2(source, scripts_dir / source.name)
    else:
        shutil.copytree(source, scripts_dir, dirs_exist_ok=True)
    return f"scripts/{entry}"


def render_index_markdown(capsule: dict[str, Any]) -> str:
    title = capsule["display_name"]
    summary = capsule["summary"]
    tags = capsule.get("tags") or capsule.get("when_to_use") or []
    meta = {
        "okf_version": OKF_VERSION,
        "type": "Video Capsule Bundle Index",
        "title": title,
        "description": summary,
        "profile": VIDEO_OKF_PROFILE,
        "primary_workflow": capsule["primary_workflow"],
        "tags": tags,
    }
    body = f"""# {title}

{summary}

# Entry

* [Capsule Card](CARD.md) - Routing summary, purpose, and usage boundary.

# Contracts

* [Input Schema](contracts/input_schema.yaml) - User input requirements and intake fields.
* [Content Scope](contracts/content_scope.yaml) - Series-fixed elements, per-episode content, and forbidden reusable literals.
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.
* [Production Contract](contracts/production_contract.yaml) - Required outputs, evidence floor, and modality gates.

# Recipes

* [Structure](recipes/structure.md) - Story beats, pacing, and scene architecture.
* [Copy](recipes/copy.md) - Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.
* [Visual](recipes/visual.md) - Visual style, references, characters, scenes, and continuity.
* [Audio](recipes/audio.md) - TTS, original audio, BGM, SFX, mix, and sync rules.
* [Motion](recipes/motion.md) - Camera motion, action, transitions, dynamic generation, and editing rhythm.

# Assets

* [Asset Index](assets/index.yaml) - Reusable packaged assets and references. Asset files are not loaded unless needed.

# Quality

* [Rules](quality/rules.yaml) - Machine-readable QA rules.
* [Release Gates](quality/release_gates.yaml) - Required checks before release.

# Learning

* [Promoted Lessons](learning/promoted_lessons.yaml) - Generalized lessons only; raw evidence remains local or archived.

# Examples

* [Illustrative Examples](examples/illustrative.yaml) - Examples for orientation only, not default final content.
"""
    return _frontmatter(meta, body)


def render_card_markdown(capsule: dict[str, Any]) -> str:
    title = capsule["display_name"]
    summary = capsule["summary"]
    tags = capsule.get("tags") or capsule.get("when_to_use") or []
    when_to_use = "\n".join(f"- {item}" for item in tags) or "- Use when this capsule matches the requested video workflow."
    when_not_to_use = "\n".join(
        f"- {item}"
        for item in (
            capsule.get("when_not_to_use")
            or [
                "Do not use when the requested output conflicts with the runtime contract.",
                "Do not copy illustrative examples as final content.",
            ]
        )
    )
    meta = {
        "type": "Video Capsule Card",
        "title": title,
        "description": summary,
        "stage": "routing",
        "profile": VIDEO_OKF_PROFILE,
        "primary_workflow": capsule["primary_workflow"],
        "tags": tags,
    }
    body = f"""# {title}

## Purpose

{summary}

## When To Use

{when_to_use}

## When Not To Use

{when_not_to_use}

## Stage Reading

- Routing: read `capsule.yaml`, `index.md`, this card, `contracts/input_schema.yaml`, and `contracts/content_scope.yaml`.
- Planning: read the input/content-scope contracts and the recipe files named under `read_order.planning`.
- Generation: read the runtime contract, motion recipe, and asset index.
- QA: read the quality rules and release gates.
- Learning: read promoted lessons only; raw evidence is local-only.
"""
    return _frontmatter(meta, body)


def render_recipe_markdown(domain: str) -> str:
    meta_source = RECIPE_META[domain]
    meta = {
        "type": "Video Recipe",
        "title": meta_source["title"],
        "description": meta_source["description"],
        "stage": meta_source["stage"],
        "domain": domain,
        "profile": VIDEO_OKF_PROFILE,
        "tags": [domain],
    }
    if domain == "copy":
        body = COPY_RECIPE_DEFAULT_BODY
    elif domain == "structure":
        body = STRUCTURE_RECIPE_DEFAULT_BODY
    else:
        body = f"# {domain.title()}\n\n## Rules\n\n{meta_source['empty_rule']}\n"
    return _frontmatter(meta, body)


def _default_runtime_contract() -> dict[str, Any]:
    return {
        "roles": {},
        "output_contract": {
            "final_video": "required",
        },
        "video_elements": {
            "fixed": {},
            "defaults": {},
            "user_overridable": {},
            "forbidden": [],
        },
        "copywriting_structure_contract": default_copywriting_structure_contract(),
    }


def _default_input_schema() -> dict[str, Any]:
    return {
        "fields": {
            "topic": {
                "type": "string",
                "required": True,
                "description": "Primary topic, subject, product, source, or brief for the video.",
            }
        }
    }


def _merge_contract_section(target: dict[str, Any], section: str, values: dict[str, Any]) -> None:
    current = target.setdefault(section, {})
    if isinstance(current, dict):
        current.update(values)


def _merge_modality_contract(target: dict[str, Any], modality: str, values: dict[str, Any]) -> None:
    modality_contracts = target.setdefault("modality_contracts", {})
    if not isinstance(modality_contracts, dict):
        modality_contracts = {}
        target["modality_contracts"] = modality_contracts
    current = modality_contracts.setdefault(modality, {})
    if isinstance(current, dict):
        current.update(values)


def _apply_format_contract_profile(
    contract: dict[str, Any],
    *,
    format_family: str,
    production_capabilities: list[str],
    quality_gate_profile: str,
) -> dict[str, Any]:
    profile = str(format_family or "").strip() or "generic_video"
    contract["format_contract_profile"] = profile
    contract["production_capabilities"] = production_capabilities
    if str(quality_gate_profile or "").strip():
        contract["quality_gate_profile"] = str(quality_gate_profile).strip()

    if profile in {"knowledge_card_explainer", "douyin_card_explainer", "high_abstraction_growth_card"}:
        _merge_contract_section(
            contract,
            "required_outputs",
            {
                "middle_vector_metaphor": "required",
                "svg_assets": "required",
                "animated_reveal": "required",
            },
        )
        _merge_modality_contract(
            contract,
            "visual",
            {
                "semantic_middle_illustration_required": True,
                "svg_asset_export_required": True,
                "source_identity_forbidden": True,
            },
        )
        _merge_modality_contract(
            contract,
            "motion",
            {
                "animated_vector_reveal_required": True,
                "static_hold_limit_seconds": 3,
            },
        )
    elif profile == "product_showcase":
        _merge_contract_section(contract, "required_outputs", {"product_evidence_board": "required"})
        _merge_modality_contract(
            contract,
            "visual",
            {
                "product_visible_first_three_seconds_required": True,
                "claim_evidence_mapping_required": True,
            },
        )
        _merge_modality_contract(
            contract,
            "motion",
            {
                "demo_sequence_required": True,
            },
        )
    elif profile == "story_drama":
        _merge_contract_section(
            contract,
            "required_outputs",
            {
                "storyboard": "required",
                "character_continuity_sheet": "required",
            },
        )
        _merge_modality_contract(
            contract,
            "visual",
            {
                "character_consistency_required": True,
                "conflict_clear_first_three_seconds_required": True,
            },
        )
    elif profile == "tutorial_screen_recording":
        _merge_contract_section(
            contract,
            "required_outputs",
            {
                "step_plan": "required",
                "result_preview": "required",
            },
        )
        _merge_modality_contract(
            contract,
            "visual",
            {
                "screen_area_readable_required": True,
                "result_preview_required": True,
            },
        )
    elif profile == "asmr_or_sensory":
        _merge_contract_section(contract, "required_outputs", {"clean_audio_review": "required"})
        _merge_modality_contract(
            contract,
            "audio",
            {
                "clean_audio_required": True,
                "loop_rhythm_review_required": True,
            },
        )
    return contract


def _default_production_contract(
    capabilities: list[str],
    evidence_level: str = "",
    *,
    format_family: str = "",
    production_capabilities: list[str] | None = None,
    quality_gate_profile: str = "",
) -> dict[str, Any]:
    capability_set = {str(item).strip().lower() for item in capabilities}
    voice_required = bool({"tts", "voice", "narration", "voiceover"} & capability_set)
    bgm_required = bool({"bgm", "music"} & capability_set)
    contract = {
        "schema_version": "capsule.production_contract.v1",
        "minimum_evidence_for_release": "L2_multimodal_probe",
        "declared_evidence_level": str(evidence_level or "unspecified").strip(),
        "evidence_policy": {
            "metadata_only_release_allowed": False,
            "visual_claims_require": "L1_metadata_plus_keyframes",
            "motion_audio_claims_require": "L2_multimodal_probe",
            "l3_requires_sample_qa": True,
        },
        "required_outputs": {
            "final_video": "required",
            "cover": "required",
            "voice": "required" if voice_required else "optional",
            "bgm": "required" if bgm_required else "optional",
            "contact_sheet": "required",
            "qa_report": "required",
            "publishing_package": "required",
        },
        "modality_contracts": {
            "copy": {
                "hook_candidates_min": 12,
                "first_3_seconds_audit_required": True,
                "title_cover_opening_alignment_required": True,
            },
            "visual": {
                "visual_component_library_required": True,
                "contact_sheet_review_required": True,
                "source_identity_forbidden": True,
            },
            "motion": {
                "motion_plan_required": True,
                "first_three_seconds_motion_or_cut_required": True,
                "static_hold_limit_seconds": 3,
            },
            "audio": {
                "voice_required": voice_required,
                "bgm_required": bgm_required,
                "silent_placeholder_forbidden": True,
            },
        },
    }
    return _apply_format_contract_profile(
        contract,
        format_family=format_family,
        production_capabilities=_dedupe(production_capabilities),
        quality_gate_profile=quality_gate_profile,
    )


def create_capsule_package(
    *,
    output_root: str | Path,
    name: str,
    display_name: str,
    summary: str,
    category: str,
    primary_workflow: str,
    capabilities: list[str],
    tags: list[str],
    status: str = "draft",
    execution_mode: str = "preset",
    version: int = 1,
    local_script: str | Path | None = None,
    local_script_entry: str = "",
    script_evidence: dict[str, Any] | str | Path | None = None,
    format_family: str = "",
    evidence_level: str = "",
    production_capabilities: list[str] | None = None,
    quality_gate_profile: str = "",
    series_fixed: list[str] | None = None,
    episode_variable: list[str] | None = None,
    forbidden_reusable_literals: list[str] | None = None,
    overwrite: bool = False,
) -> Path:
    capsule_name = _validate_capsule_name(name)
    out_root = Path(output_root).expanduser().resolve()
    cap_dir = (out_root / f"{capsule_name}.capsule").resolve()
    if cap_dir.parent != out_root:
        raise SystemExit(f"capsule output escapes output root: {cap_dir}")
    clean_capabilities = _dedupe(capabilities)
    if not clean_capabilities:
        raise SystemExit("at least one capability is required")
    clean_tags = _dedupe(tags)
    clean_production_capabilities = _dedupe(production_capabilities)
    if not str(display_name).strip():
        raise SystemExit("display_name is required")
    if not str(summary).strip():
        raise SystemExit("summary is required")
    if not str(primary_workflow).strip():
        raise SystemExit("primary_workflow is required")

    execution_mode_value = str(execution_mode or "preset").strip()
    if local_script:
        execution_mode_value = "local_script"
    if execution_mode_value not in ALLOWED_EXECUTION_MODES:
        raise SystemExit(
            "execution_mode must be one of: " + ", ".join(sorted(ALLOWED_EXECUTION_MODES))
        )
    if execution_mode_value == "local_script" and not local_script:
        raise SystemExit("execution_mode=local_script requires local_script")
    if local_script:
        validated_source, _ = _validate_local_script_source(
            local_script,
            local_script_entry=local_script_entry,
        )
        if validated_source == cap_dir or validated_source.is_relative_to(cap_dir):
            raise SystemExit("local_script source must be outside the target capsule package")
        try:
            normalize_script_evidence(load_script_evidence(script_evidence))
        except (CapsuleScriptPolicyError, OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"local_script requires reusable evidence: {exc}") from exc
        clean_capabilities = _dedupe([*clean_capabilities, "local_script"])

    if cap_dir.exists():
        if not overwrite:
            raise SystemExit(f"capsule package already exists: {cap_dir}")
        shutil.rmtree(cap_dir)

    cap_dir.mkdir(parents=True, exist_ok=True)
    entrypoints = {"preset": "general_video"}

    if local_script:
        entrypoints["local_script"] = install_local_script_bundle(
            cap_dir,
            local_script,
            local_script_entry=local_script_entry,
        )

    capsule = {
        "schema_version": "capsule.package.v1",
        "profile": VIDEO_OKF_PROFILE,
        "name": capsule_name,
        "display_name": str(display_name).strip(),
        "version": int(version),
        "status": str(status or "draft").strip(),
        "execution_mode": execution_mode_value,
        "category": str(category or "").strip(),
        "primary_workflow": str(primary_workflow).strip(),
        "summary": str(summary).strip(),
        "capabilities": clean_capabilities,
        "tags": clean_tags,
        "when_to_use": clean_tags,
        "when_not_to_use": [],
        "read_order": DEFAULT_READ_ORDER,
        "entrypoints": entrypoints,
    }
    if str(format_family or "").strip():
        capsule["format_family"] = str(format_family).strip()
    if str(evidence_level or "").strip():
        capsule["evidence_level"] = str(evidence_level).strip()
    if clean_production_capabilities:
        capsule["production_capabilities"] = clean_production_capabilities
    if str(quality_gate_profile or "").strip():
        capsule["quality_gate_profile"] = str(quality_gate_profile).strip()

    _dump_yaml(cap_dir / "capsule.yaml", capsule)
    _write_text(cap_dir / "index.md", render_index_markdown(capsule))
    _write_text(cap_dir / "CARD.md", render_card_markdown(capsule))
    _dump_yaml(cap_dir / "contracts" / "runtime.yaml", _default_runtime_contract())
    _dump_yaml(cap_dir / "contracts" / "input_schema.yaml", _default_input_schema())
    content_scope = default_content_scope_contract()
    if series_fixed is not None:
        content_scope["series_fixed"] = _dedupe(series_fixed)
    if episode_variable is not None:
        content_scope["episode_variable"] = _dedupe(episode_variable)
    if forbidden_reusable_literals is not None:
        content_scope["forbidden_reusable_literals"] = _dedupe(forbidden_reusable_literals)
    _dump_yaml(cap_dir / "contracts" / "content_scope.yaml", content_scope)
    _dump_yaml(
        cap_dir / "contracts" / "production_contract.yaml",
        _default_production_contract(
            clean_capabilities,
            evidence_level,
            format_family=str(format_family or "").strip() or str(category or "").strip(),
            production_capabilities=clean_production_capabilities,
            quality_gate_profile=quality_gate_profile,
        ),
    )
    for domain in ("structure", "copy", "visual", "audio", "motion"):
        _write_text(cap_dir / "recipes" / f"{domain}.md", render_recipe_markdown(domain))
    _dump_yaml(
        cap_dir / "quality" / "rules.yaml",
        {
            "rules": [
                {
                    "id": "final_video_required",
                    "type": "artifact_required",
                    "severity": "blocker",
                    "category": "final_video",
                    "rule": "Final video must be produced before release.",
                },
                {
                    "id": "copywriting_structure_contract_required",
                    "type": "copy_gate",
                    "severity": "blocker",
                    "category": "copy",
                    "rule": "Planning must produce the capsule copywriting structure contract before generation: topic angle, first 3 seconds, first 20 seconds, script outline, cover text, title, and risk notes.",
                },
                {
                    "id": "first_three_seconds_hook_required",
                    "type": "copy_gate",
                    "severity": "blocker",
                    "category": "copy",
                    "rule": "The real first 0-3 seconds must contain concrete pain, identity pressure, a counterintuitive verdict, a status/control stake, or a completion gap.",
                },
            ]
        },
    )
    _dump_yaml(
        cap_dir / "quality" / "release_gates.yaml",
        {
            "gates": [
                "final_video_required",
                "copywriting_structure_contract_required",
                "first_three_seconds_hook_required",
            ]
        },
    )
    _dump_yaml(cap_dir / "assets" / "index.yaml", {"assets": []})
    _dump_yaml(cap_dir / "learning" / "promoted_lessons.yaml", {"lessons": []})
    _dump_yaml(cap_dir / "examples" / "illustrative.yaml", {"examples": []})

    report = validate_capsule_dir(cap_dir, warnings_ok=True)
    if not report["ok"]:
        raise SystemExit("created capsule failed validation: " + "; ".join(report["errors"]))
    return cap_dir


def _split_csv(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for raw in values or []:
        result.extend(item.strip() for item in str(raw).split(",") if item.strip())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Video OKF capsule package.")
    parser.add_argument("--out", default="capsules")
    parser.add_argument("--name", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--primary-workflow", required=True)
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--status", default="draft")
    parser.add_argument("--execution-mode", default="preset")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--local-script", default="")
    parser.add_argument("--local-script-entry", default="")
    parser.add_argument(
        "--script-evidence",
        default="",
        help="JSON object or path proving successful runs, cross-topic reuse, deterministic steps, and parameterized inputs.",
    )
    parser.add_argument("--format-family", default="")
    parser.add_argument("--evidence-level", default="")
    parser.add_argument("--production-capability", action="append", default=[])
    parser.add_argument("--quality-gate-profile", default="")
    parser.add_argument(
        "--series-fixed",
        action="append",
        default=None,
        help="Repeat or pass comma-separated names for stable series-level elements.",
    )
    parser.add_argument(
        "--episode-variable",
        action="append",
        default=None,
        help="Repeat or pass comma-separated names for current-episode input fields.",
    )
    parser.add_argument(
        "--forbidden-reusable-literal",
        action="append",
        default=None,
        help="Repeat for known episode literals that must not enter reusable package surfaces.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cap_dir = create_capsule_package(
        output_root=args.out,
        name=args.name,
        display_name=args.display_name,
        summary=args.summary,
        category=args.category,
        primary_workflow=args.primary_workflow,
        capabilities=_split_csv(args.capability),
        tags=_split_csv(args.tag),
        status=args.status,
        execution_mode=args.execution_mode,
        version=args.version,
        local_script=args.local_script or None,
        local_script_entry=args.local_script_entry,
        script_evidence=args.script_evidence or None,
        format_family=args.format_family,
        evidence_level=args.evidence_level,
        production_capabilities=_split_csv(args.production_capability),
        quality_gate_profile=args.quality_gate_profile,
        series_fixed=_split_csv(args.series_fixed) if args.series_fixed is not None else None,
        episode_variable=_split_csv(args.episode_variable) if args.episode_variable is not None else None,
        forbidden_reusable_literals=(
            _split_csv(args.forbidden_reusable_literal)
            if args.forbidden_reusable_literal is not None
            else None
        ),
        overwrite=args.overwrite,
    )
    payload = {"ok": True, "capsule_dir": str(cap_dir)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"created capsule package: {cap_dir}")


if __name__ == "__main__":
    main()
