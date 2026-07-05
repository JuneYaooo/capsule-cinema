# Video Distillation Output Schema

## Required Run Layout

Run directories must be named `output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>/`.

```text
<run_dir>/
├── 00_source/
├── 01_media/
├── 02_transcript/
├── 03_keyframes/
├── 04_gemini/
├── 05_copy/
├── 06_video_logic/
├── 07_production_logic/
├── 08_synthesis/
├── evidence_map.json
└── artifact_manifest.json
```

`evidence_map.json` must report the highest fully completed level. If transcript or multimodal review is missing, downstream generated artifacts may still exist, but their stages must be marked `limited` and the top-level `evidence_level` must stop at the highest preceding `present` level.

## Copy Logic

`05_copy/copy_logic.yaml` uses schema `capsule_cinema.video_copy_logic.v1` and must include `hook`, `promise`, `script_structure`, `copy_devices`, `cta`, `rewrite_template`, and `confidence`.

## Beat Timeline

`06_video_logic/beat_timeline.json` uses schema `capsule_cinema.video_beat_timeline.v1` and must include `beats` plus `logic_summary.core_loop`, `viewer_question_opened`, `viewer_question_closed`, `main_retention_device`, and `weak_points`.

## Production Logic

`07_production_logic/production_logic.yaml` uses schema `capsule_cinema.video_production_logic.v1` and must include `visual_style`, `motion_and_editing` or `motion_style`, `audio_logic`, `production_route`, `cheapest_viable_route`, `highest_fidelity_route`, `recommended_route`, `required_materials`, `replaceable_materials`, `hardest_part_to_reproduce`, `quality_risks`, and `do_not_copy`. Each visual, motion, audio, route, and production-route summary claim must include concrete timestamps or time ranges, transcript snippets, frame/keyframe paths, media-info refs, or explicit inference markers. Placeholder-only evidence fields are invalid.

## Recipe Seed

`08_synthesis/recipe_seed.yaml` uses schema `capsule_cinema.video_distillation_recipe_seed.v1`. It must not include source account identity, copied source script, signed media URLs, API keys, or private token values.
