# drawio-skill Repo Showcase Video Design

Date: 2026-07-04

## Goal

Create a default `repo_showcase` capsule video for `Agents365-ai/drawio-skill`.
The video should introduce the project as a practical Agent Skill for turning
natural language, codebases, infrastructure, SQL schemas, and Mermaid into
editable draw.io diagrams.

## Source Facts

- Repo: `Agents365-ai/drawio-skill`
- User-provided proof numbers: 5063 stars, 1 issue, 64 forks, 12 pull requests,
  52 contributors.
- README promise: generates `.drawio` XML from natural language and exports PNG,
  SVG, PDF, and JPG via the native draw.io desktop CLI.
- README capabilities: diagram presets, Mermaid to native draw.io, codebase
  visualization, infrastructure diagrams from Terraform/Kubernetes/docker-compose,
  SQL DDL to ER diagrams, deterministic sequence diagrams, C4 drill-down,
  official shape search, AI/LLM logos, visual self-check, and iterative feedback.
- README compatibility: Claude Code, Cursor, Copilot, OpenClaw, Codex,
  Autohand Code, Hermes, and Agent Skills-compatible agents.

## Audience

Primary users:

- Developers and architects who need architecture, infra, ERD, C4, or sequence
  diagrams without hand-positioning every node.
- Agent/Codex/Claude Code users who want a skill they can install and call from
  a coding session.
- Technical content creators or maintainers who need repeatable, editable
  diagrams for README, docs, PR summaries, or slide exports.

Wrong audience:

- Viewers expecting a generic AI image generator.
- Viewers expecting guaranteed design quality without reviewing the exported
  diagram.
- Viewers who only need static screenshots and do not care about editable
  `.drawio` output.

## Format

- Capsule: `capsules/repo_showcase.capsule`
- Route: `short_silent_repo_showcase`
- Aspect ratio: 3:4, 1080 x 1440
- Duration: 8-10 seconds
- Scene count: 5
- Audio: packaged Manten Diloty BGM only
- Voiceover: none
- Burned subtitles: none
- Layout: repo_showcase dark grid card system
- Identity badge: `Agents365-ai/drawio-skill`

## Hook

Working main hook:

> 5k 星的 draw.io Skill，把仓库和架构画成可编辑图

Subtitle direction:

> 自然语言、代码库、IaC、SQL、Mermaid 都能进 draw.io

Rationale:

- The 5063-star proof is strong enough to appear early, but it must not replace
  the core transformation.
- The memory anchor is `draw.io Skill`, a familiar diagram tool plus an Agent
  Skill wrapper.
- The core transformation is turning messy technical inputs into editable
  diagrams, not just "AI draws pictures".

## Storyboard

Scene 1: Trust and task fit

- Middle visual: GitHub/README hero area or project title cropped without URL.
- Bottom fact chain:
  - 5k 星先让人停一下
  - 重点不是又一个画图 prompt
  - 它把技术材料变 draw.io
  - 输出还能继续编辑和导出
  - 适合要交付图的人

Scene 2: Natural language to diagram

- Middle visual: README microservices example or demo image.
- Bottom fact chain:
  - 先用一句话描述架构
  - Skill 生成 .drawio XML
  - 再导出 PNG/SVG/PDF/JPG
  - 图能改，不是死截图
  - 文档和汇报都能接上

Scene 3: Code and infra inputs

- Middle visual: README section showing code/IaC extractors or a cropped source
  section proving importer breadth.
- Bottom fact chain:
  - 它不只吃自然语言
  - Python/JS/Go/Rust 可分析
  - Terraform/K8s/Compose 可成图
  - SQL 还能转 ER 关系
  - 复杂仓库少靠手摆线

Scene 4: Differentiator

- Middle visual: README highlights for official shapes, AI/LLM logos, visual
  self-check, or demo topology examples.
- Bottom fact chain:
  - 难点常在图标和布局
  - 它能搜官方 shapes
  - 还有 AI/LLM 品牌标识
  - 自检会盯重叠和裁字
  - 但最终仍要人审图

Scene 5: Practical handoff

- Middle visual: installation/quick-start or compatibility badges cropped to
  avoid URLs.
- Bottom fact chain:
  - 把仓库装进你的 Agent
  - 给它材料和想要的图型
  - 先拿可编辑 draw.io 初稿
  - 再按团队风格迭代
  - 适合沉淀工程文档

## Material Plan

Use the repo_showcase material ladder:

1. Prefer repository-provided assets from README and `assets/`, especially the
   hero microservices example and topology demo images.
2. Use README rendered-content screenshots only when source assets are not
   enough to prove a scene.
3. Crop out browser chrome, URLs, domains, sidebars, and file lists.
4. Avoid generated summary cards in the first approved release unless real
   material is inaccessible.
5. Create a source asset manifest listing every middle visual and whether it is
   actual source material or fallback.

## Tool Chain

- Source audit: local clone or direct GitHub raw assets.
- Rendering: `capsules/repo_showcase.capsule/scripts/render_repo_showcase_video.py`
- BGM: `capsules/repo_showcase.capsule/assets/manten_diloty_bgm_cut_37sec.mp3`
- QA: local video QA, contact sheet review, visible text lint, and self-media
  compliance review.
- Publishing package: title options, cover text, platform copy, pinned comment,
  and release manifest.

No generative image or video provider is needed for the default version.

## Public Copy Constraints

- Do not show full URLs, domains, QR codes, "source", "draft", "v1", or
  production/revision language.
- Do not use generic titles such as "GitHub project recommendation" or
  "AI drawing tool".
- Do not promise fully automatic architecture correctness.
- Keep proof numbers tied to the actual user result.
- Keep public language in viewer terms: input material, editable diagram,
  exported assets, docs, PRs, and engineering handoff.

## QA Gates

- Final video is 1080 x 1440 and 8-10 seconds.
- Final audio has BGM and no voiceover.
- Five scenes are readable on a phone preview.
- Top identity accurately shows `Agents365-ai/drawio-skill`.
- Middle visuals are actual source material for at least four scenes.
- Bottom cards contain 4-5 useful short lines per scene.
- Visible text lint passes with no internal planning terms.
- Compliance review has no blocker or unresolved high risk.
- Release package contains public, qa, technical, and internal artifacts plus
  `CURRENT_RELEASE.md` and `release_manifest.json`.

## Deliverables

Expected release package:

```text
output/drawio-skill-repo-showcase/
  CURRENT_RELEASE.md
  release/<version_slug>/
    README.md
    release_manifest.json
    public/
      final video
      cover/copy assets
      platform copy
    qa/
      QA report
      visible copy lint report
      compliance report
      contact sheet
    technical/
      ffprobe/render notes
      source asset manifest
    internal/
      audience pull card
      user-first brief
      hook/title bakeoff
      storyboard/profile
```

## Self-Review

- No unfinished markers remain.
- The scope is one repo, one default capsule video, one release package.
- The storyboard follows the approved default route: silent, 3:4, 5 scenes,
  under 10 seconds.
- Tool use is deterministic local rendering; no unapproved media generation
  channel is required.
- Claims are limited to facts from the user-provided row and the repository
  README, with an explicit human-review boundary.
