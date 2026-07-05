---
name: video-distillation
description: Use when deep-distilling a selected social video, short-form winner post, Douyin/Bilibili/XHS/TikTok video, copied share URL, or local video into evidence-backed 文案逻辑, 整个视频逻辑, 画面风格, 动效, audio/TTS/digital-human needs, production route, and reusable recipe seed.
---

# Video Distillation

Deep-distill selected social videos into source-grounded copy logic, whole-video logic, visual/motion/audio logic, and a production-route playbook. Use this skill for 深度视频蒸馏 when the output needs to become a reusable production recipe seed.

This skill is independent from Capsule Cinema runtime. Do not write run outputs into `video-distillation/`, `capsules/`, or root `skill.md`. Bind evidence runs to `output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>/`, for example `output/video_distillation/20260704_153012_sample_title/`.

## Read When Needed

- Protocol and evidence levels: [references/video-distillation-protocol.md](references/video-distillation-protocol.md)
- Artifact schemas: [references/output-schema.md](references/output-schema.md)
- Gemini and keyframe prompts: [references/gemini-video-analysis-prompts.md](references/gemini-video-analysis-prompts.md)
- External extractor contract: [references/extraction-tool-contract.md](references/extraction-tool-contract.md)

## Non-Negotiables

- Do not call a result deep if it only has title/caption/metrics.
- Separate `observed`, `inferred`, and `recommended` claims.
- For 文案逻辑, analyze title, caption, cover/opening text, subtitle/OCR, spoken opening, transcript structure, CTA, and rewrite mechanism.
- For 整个视频逻辑, analyze first frame, 0-1s, 1-3s, 3-5s, 5-8s, setup, promise, proof/demo/story progression, payoff, CTA, ending, and segment-level retention roles.
- For production route, classify whether reproduction needs AI image generation, AI video generation, digital human, TTS, human voiceover, screen recording, local card rendering, motion graphics, subtitles, BGM, SFX, or manual editing.
- Never copy the source script, account identity, watermark, handle, logo, or source frames into reusable recipes.

## Default Workflow

1. Create a run directory named `<YYYYMMDD_HHMMSS>_<slug>` under `output/video_distillation/`.
2. Acquire media with `scripts/distill_video.py --url` or `--local-video`.
3. Preserve raw source status, media info, transcript, keyframes, Gemini output, copy logic, video logic, production logic, synthesis, evidence map, and manifest.
4. Mark the evidence depth from `V0_metadata_only` through `V6_recipe_seed_ready`.
5. Use `08_synthesis/recipe_seed.yaml` only as a production planning seed, not as an active capsule.

## Commands

Local video:

```bash
python video-distillation/scripts/distill_video.py \
  --local-video /path/to/video.mp4 \
  --transcript-text "optional known transcript" \
  --output-root output/video_distillation \
  --disable-gemini
```

Social URL or copied share text (pass copied share text to `--url`):

```bash
python video-distillation/scripts/distill_video.py \
  --url "https://v.douyin.com/example/" \
  --external-video-workflow-root /Users/june2/code/github/video_workflow \
  --dotenv-path /Users/june2/code/github/video_workflow/.env
```

## Response Rules

- Lead with the highest completed evidence level and missing layers.
- Cite local artifact paths for each major claim.
- State if production-route fields are observed or inferred.
- If extractor/Gemini fails, report the failed stage and fallback path instead of pretending the video was deeply reviewed.
