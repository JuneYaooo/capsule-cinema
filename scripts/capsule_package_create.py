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


VIDEO_OKF_PROFILE = "video.okf.capsule.v1"
OKF_VERSION = "0.1"
SAFE_CAPSULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

DEFAULT_READ_ORDER = {
    "routing": ["index.md", "CARD.md", "contracts/input_schema.yaml"],
    "planning": [
        "contracts/input_schema.yaml",
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
* [Runtime Contract](contracts/runtime.yaml) - Tool roles, execution constraints, and output contract.

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

- Routing: read `capsule.yaml`, `index.md`, this card, and `contracts/input_schema.yaml`.
- Planning: read `contracts/input_schema.yaml` and the recipe files named under `read_order.planning`.
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
        "defaults": {
            "copywriting_structure_contract": default_copywriting_structure_contract(),
        },
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
    overwrite: bool = False,
) -> Path:
    capsule_name = _validate_capsule_name(name)
    out_root = Path(output_root).expanduser().resolve()
    cap_dir = (out_root / f"{capsule_name}.capsule").resolve()
    if cap_dir.parent != out_root:
        raise SystemExit(f"capsule output escapes output root: {cap_dir}")
    if cap_dir.exists():
        if not overwrite:
            raise SystemExit(f"capsule package already exists: {cap_dir}")
        shutil.rmtree(cap_dir)

    clean_capabilities = _dedupe(capabilities)
    if not clean_capabilities:
        raise SystemExit("at least one capability is required")
    clean_tags = _dedupe(tags)
    if not str(display_name).strip():
        raise SystemExit("display_name is required")
    if not str(summary).strip():
        raise SystemExit("summary is required")
    if not str(primary_workflow).strip():
        raise SystemExit("primary_workflow is required")

    cap_dir.mkdir(parents=True, exist_ok=True)
    entrypoints = {"preset": "general_video"}
    execution_mode_value = str(execution_mode or "preset").strip()

    if local_script:
        source = Path(local_script).expanduser()
        if not source.is_file():
            raise SystemExit(f"local_script source file missing: {local_script}")
        dest = cap_dir / "scripts" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        entrypoints["local_script"] = f"scripts/{source.name}"
        execution_mode_value = "local_script"

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

    _dump_yaml(cap_dir / "capsule.yaml", capsule)
    _write_text(cap_dir / "index.md", render_index_markdown(capsule))
    _write_text(cap_dir / "CARD.md", render_card_markdown(capsule))
    _dump_yaml(cap_dir / "contracts" / "runtime.yaml", _default_runtime_contract())
    _dump_yaml(cap_dir / "contracts" / "input_schema.yaml", _default_input_schema())
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
        overwrite=args.overwrite,
    )
    payload = {"ok": True, "capsule_dir": str(cap_dir)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"created capsule package: {cap_dir}")


if __name__ == "__main__":
    main()
