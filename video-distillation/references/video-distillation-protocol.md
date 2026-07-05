# Video Distillation Protocol

Use this protocol for selected winner videos, local short videos, and social share URLs that need deep production-method distillation.

## Evidence Levels

- `V0_metadata_only`: title, caption, tags, stats, and source URL only.
- `V1_media_acquired`: local video, cover, extractor JSON, and media info exist.
- `V2_transcript_ready`: transcript exists and supports copy/script analysis.
- `V3_keyframe_ready`: opening and representative keyframes/contact sheet exist.
- `V4_multimodal_reviewed`: Gemini-class full-video review or equivalent plus keyframe analysis exists.
- `V5_production_logic_distilled`: copy, whole-video logic, visual/motion/audio logic, and production route are classified with evidence.
- `V6_recipe_seed_ready`: reusable recipe seed exists without copied source identity or script.

## Required Deep Layers

Deep means all of these are attempted and explicitly marked as complete, limited, or failed:

1. source acquisition;
2. media info;
3. transcript;
4. keyframes/contact sheet;
5. Gemini or equivalent video analysis;
6. copy logic;
7. whole-video logic;
8. production-route logic;
9. synthesis and recipe seed.

## Run Layout

Write every run under `output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>/` with the numbered folders defined in `references/output-schema.md`, for example `output/video_distillation/20260704_153012_sample_title/`.

## Evidence Discipline

Every major claim must cite one or more concrete evidence anchors:

- transcript snippet;
- timestamp or time range;
- frame path;
- media-info reference;
- Gemini observation that includes a timestamp, frame path, transcript snippet, or media-info reference;
- explicit inference label when the claim is not directly observed.

Gemini observations are not standalone evidence. If a Gemini observation lacks a timestamp, frame path, transcript snippet, or media-info reference, mark the claim as inference.

Do not infer camera motion, edit rhythm, voice style, BGM, digital human use, or AI generation route from metadata only.
