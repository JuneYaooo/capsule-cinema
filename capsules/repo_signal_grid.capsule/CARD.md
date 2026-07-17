---
type: Video Capsule Card
title: Repo Signal Grid
description: 通用 GitHub/AI Skills 价值展示 + 6:7 全画布连续白底橙网格模板；用于 repo、工具和 Agent Skill 展示。
stage: routing
profile: video.okf.capsule.v1
primary_workflow: repo_signal_grid_video
tags:
- github
- ai-tool
- wechat-channels
- value-extraction
- visual-template
- template-clone
- safe-area
- 6-7
---

# Repo Signal Grid

## Purpose

通用 GitHub/AI Skills 价值展示 + 6:7 全画布连续白底橙网格模板；用于 repo、工具和 Agent Skill 展示。

## When To Use

- github
- ai-tool
- wechat-channels
- value-extraction
- visual-template
- template-clone
- safe-area
- 6-7

## Approved Source Path

- **Strict Browser-Only:** build every approved middle scene from an actual browser-opened GitHub/X/project page screenshot. Each approved scene must use a `capture_method` that starts with `actual_browser_`; copied, downloaded, extracted, QuickLook, local README render, PIL, HTML, or source-card materials are diagnostic-only and cannot enter an approved release.
- Use the source priority `1 4 3 2`: `1` GitHub repo/README browser key-area screenshots, `4` browser screenshots of visible README image/page elements, `3` X search or public discussion browser screenshots, then `2` external project/docs/demo/release pages opened in the browser.
- Put a real browser README/GitHub key-area screenshot first when available. It must show README content, stars, repo description, or another useful key area, not a file list or locally simulated Markdown/HTML/PIL render.
- Before every capture, name the single README/result/table/UI region that proves the scene. Prefer a tightly framed browser capture where this core region occupies at least 65% of the screenshot. Remove browser shell, sticky navigation, sidebars, file lists, addresses, blank margins, and unrelated page context without removing labels or comparisons needed to understand the evidence.
- If broader page context must remain, record `capture_scope: context_plus_core` and `core_region_description`, then set the scene's `core_focus` and `motion_direction: local_zoom`. A broad full-page capture with no named core focus is not approved.
- Use a landscape responsive capture aligned with the horizontal middle panel. Phone-portrait captures are reserved for projects whose evidence is itself a mobile UI.
- Generic documentation/source screenshots stay diagnostic-only; `browser_evidence_screenshot` is the approved type for first-frame browser evidence only when it comes from an actual browser capture.
- An approved release requires `source_asset_manifest` entries with `actual_source: true`, `reconstructed_card: false`, existing local paths, `actual_browser_*` capture methods, scene image mappings, and 4 browser-captured middle visuals.
- The compatibility escape hatch `REPO_SHOWCASE_REQUIRE_BROWSER_SCREENSHOTS=0` is only for diagnostic or legacy reproduction runs. It must not be used to approve a user-facing repo_signal_grid release.
- 默认成片固定 15 秒；画布固定为 1080×1260（6:7），主要从原 9:16 方案压缩纵向高度。标题、素材、正文和来源脚注限制在 y=30..1230，但暖白底、橙色网格和光晕连续覆盖完整画布，不画上下空白带。中间主视觉优先直接截取能证明本幕判断的核心区域；只有多个区域的先后关系本身有意义时才做上下滑或左右滑，保留完整上下文时用局部放大锁定证据。
- 渲染前必须用 GitHub API 刷新 star 数；API 失败时才能回退选题表旧值，并在 batch report/profile 写清 `stars_source` 和 `stars_checked_at`。

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
