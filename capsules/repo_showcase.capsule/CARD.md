---
type: Video Capsule Card
title: GitHub Skills Showcase
description: 通用 GitHub/AI Skills 价值展示 + 视频号 3:4 视觉模板；用于 repo、工具和 Agent Skill 展示。
stage: routing
profile: video.okf.capsule.v1
primary_workflow: repo_showcase_video
tags:
- github
- ai-tool
- wechat-channels
- value-extraction
- visual-template
- template-clone
---

# GitHub Skills Showcase

## Purpose

通用 GitHub/AI Skills 价值展示 + 视频号 3:4 视觉模板；用于 repo、工具和 Agent Skill 展示。

## When To Use

- github
- ai-tool
- wechat-channels
- value-extraction
- visual-template
- template-clone

## Approved Source Path

- Build each middle scene from a traceable source asset: repository image, README/docs embedded image, documentation screenshot, source/example/config file screenshot, demo/output screenshot, or GIF/video frame.
- When rich media is missing, fall back through real README/docs/source content screenshots before deciding the run is blocked.
- An approved release requires `source_asset_manifest` entries with `actual_source: true`, `reconstructed_card: false`, existing local paths, capture methods, and scene image mappings.

## When Not To Use

- Do not use when the requested output conflicts with the runtime contract.
- Do not copy illustrative examples as final content.
- Do not use this capsule for an approved release when the middle visuals cannot be backed by the approved source path.
- Do not create a separate visible bottom title; the bottom area is only the 4-5 line fact chain plus a small source footer.

## Stage Reading

- Routing: read `capsule.yaml`, `index.md`, this card, and `contracts/input_schema.yaml`.
- Planning: read `contracts/input_schema.yaml` and the recipe files named under `read_order.planning`.
- Generation: read the runtime contract, motion recipe, and asset index.
- QA: read the quality rules and release gates.
- Learning: read promoted lessons only; raw evidence is local-only.
