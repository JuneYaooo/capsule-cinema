---
type: Video Capsule Card
title: Repo Signal Grid
description: 通用 GitHub/AI Skills 价值展示 + 6:7 全画布连续白底橙网格模板；保留原仓库截图，并在原图表现力不足时补充可披露的模拟产出图或 SVG 结构图。
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

通用 GitHub/AI Skills 价值展示 + 6:7 全画布连续白底橙网格模板；用于 repo、工具和 Agent Skill 展示。每条成片至少保留一张原仓库截图；其余原图表达力不足时，可补充贴合仓库风格且明确披露的模拟产出图或 SVG 结构图。

## When To Use

- github
- ai-tool
- wechat-channels
- value-extraction
- visual-template
- template-clone
- safe-area
- 6-7

## Approved Visual Path

- **Original evidence + disclosed illustration:** retain at least one real browser screenshot from the repository/README or Factory-rendered locked repository page in every approved release. Other scenes may use browser evidence, representative X/Reddit discussion screenshots, source-grounded simulated output visuals, or editable SVG explainers when the repository's own images are too weak to communicate the point.
- Audit the repository first. Scene one always follows the README opening ladder. For later scenes, prefer README-visible images/video, then X discussion, SVG, Chinese repository text, and plain English. Legacy capability simulations may reproduce older runs but are outside this new priority ladder.
- If the repository is mainly long-form text, choose the path, relationship, decision, or architecture view that best explains this episode's value, then turn it into a clear SVG. Keep the editable SVG and export a PNG preview for the renderer.
- Generated visuals are not evidence. Mark them visibly as `能力模拟` or `结构示意`; set `actual_source: false`, `synthetic: true`, and provide `evidence_basis` and `style_basis`. Do not invent unsupported functions, numbers, endorsements, or exact project results.
- Use the position-aware opening-image and later-image ladders below; they supersede the legacy `1 4 3 2 + generated fallback` ordering.
- For Chinese-facing output, use two position-aware ladders. Opening image: official Chinese README, then the README translated in a real browser with Google Translate, then the original rendered README. Later images: browser-visible README images/video, relevant X discussion screenshots, a disclosed editable SVG explainer, Chinese repository text screenshots, and finally plain-English screenshots. Google-translated captures must be identified as translated views in the manifest rather than official Chinese sources.
- Put the README ladder capture in scene one; generated visuals cannot replace the opening. It must show rendered README content or project identity, not a file list or locally simulated Markdown/HTML/PIL render.
- Before every capture, name the single README/result/table/UI region that proves the scene. Prefer a tightly framed browser capture where this core region occupies at least 65% of the screenshot. Remove browser shell, sticky navigation, sidebars, file lists, addresses, blank margins, and unrelated page context without removing labels or comparisons needed to understand the evidence.
- If broader page context must remain, `capture_scope`, `core_region_description`, `core_focus` and `motion_direction` may guide motion, but missing hints do not invalidate otherwise traceable, readable evidence. The Factory visual gate judges the real pixels once.
- Use a landscape responsive capture aligned with the horizontal middle panel. Phone-portrait captures are reserved for projects whose evidence is itself a mobile UI.
- Generic documentation/source screenshots stay diagnostic-only; `browser_evidence_screenshot` is the approved type for first-frame browser evidence only when it comes from an actual browser capture.
- An approved release requires `source_asset_manifest` entries for every used middle visual, existing local paths, scene image mappings, at least one repository/locked-page browser screenshot, and explicit provenance/disclosure for generated items.
- The compatibility escape hatch `REPO_SHOWCASE_REQUIRE_BROWSER_SCREENSHOTS=0` is only for diagnostic or legacy reproduction runs. It must not be used to approve a user-facing repo_signal_grid release.
- 默认成片固定 15 秒；画布固定为 1080×1260（6:7），主要从原 9:16 方案压缩纵向高度。标题、素材、正文和来源脚注限制在 y=30..1230，但暖白底、橙色网格和光晕连续覆盖完整画布，不画上下空白带。中间主视觉优先直接截取能证明本幕判断的核心区域；只有多个区域的先后关系本身有意义时才做上下滑或左右滑，保留完整上下文时用局部放大锁定证据。
- 渲染前必须用 GitHub API 刷新 star 数；API 失败时才能回退选题表旧值，并在 batch report/profile 写清 `stars_source` 和 `stars_checked_at`。

## When Not To Use

- Do not use when the requested output conflicts with the runtime contract.
- Do not copy illustrative examples as final content.
- Do not use this capsule for an approved release when no original repository screenshot can be captured or when generated visuals cannot be grounded in repository facts.
- Do not create a separate visible bottom title; the bottom area is only the 4-5 line fact chain plus a small source footer.

## Stage Reading

- Routing: read `capsule.yaml`, `index.md`, this card, and `contracts/input_schema.yaml`.
- Planning: read `contracts/input_schema.yaml` and the recipe files named under `read_order.planning`.
- Generation: read the runtime contract, motion recipe, and asset index.
- QA: read the quality rules and release gates.
- Learning: read promoted lessons only; raw evidence is local-only.
