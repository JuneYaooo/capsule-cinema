---
type: Video Recipe
title: Visual Recipe
description: Visual style, references, characters, scenes, composition, and continuity.
stage: planning
domain: visual
profile: video.okf.capsule.v1
tags:
- visual
---

# Visual

## Rules

- Use the repo_showcase renderer's 3:4 dark grid card system unless the user asks for a different delivery format.
- Top identity must make the exact subject visible. Prefer `owner/repo` for a repo, or a short Skill path when the video is about one Skill. `REPO SHOWCASE`, `GitHub 项目`, `AI 工具` and similar labels are not enough by themselves.
- If the video actually covers several Skills/modules/tools, keep the title focused on the shared user result and use a dedicated subject list area with `subject_paths`; show 3-5 个代表短路径, not a cramped title or middle-image overlay.
- The top subtitle must stay phone-readable and must not collide with the material area. For 3:4 renders, keep it around 34-38px, 推荐 36px, and verify the first/contact-sheet frame has clear space between subtitle and middle panel.
- Middle visuals are a pure source-material area by default. Do not add a repeated middle title above the image unless a profile or scene explicitly sets `show_middle_title: true`; do not overlay image labels unless `show_image_labels: true`.
- Approved middle visual contract: every approved middle image must be a traceable real source asset. Each scene image maps to `source_asset_manifest` with `actual_source: true`, `reconstructed_card: false`, an existing local `path`, and a concrete `capture_method`.
- Allowed source asset types: `repository_image`, `readme_embedded_image`, `documentation_screenshot`, `source_file_screenshot`, `demo_output_screenshot`, `video_or_gif_frame`.
- Source priority: choose repository-owned rich visuals first, including README/docs demo images, output images, UI screenshots, PPT/report result images, before/after images, charts, GIF/video frames, galleries, and theme previews.
- Real page fallback: when rich visuals are missing or do not prove the claim, capture a real README/docs/official/project-party content area, cropped so address bars, URLs, sidebars, browser chrome, QR codes, and generic file lists stay out of frame.
- Fallback order when no rich media exists: first capture a README content screenshot that names the behavior or output; second capture a docs page screenshot; third capture a source/example/config file screenshot that proves the mechanism; fourth capture a repository file tree only when paired with a readable README or source excerpt.
- If the audit cannot produce enough real source assets for the scene count, fail the approved render and leave a blocked/preview note. A generated or retyped card belongs outside approved repo_showcase output.
- Pure background, blank texture, or decorative imagery is not enough middle material unless it is the project's own visible result and contains understandable information.
- Crop or mask visible URLs, domains, browser chrome, QR codes, and link prompts. If a screenshot cannot be cleaned without losing the point, choose another source.
- Let visual motion serve readability. Long vertical assets can move on the long axis; dense UI, tables, diagrams, and thumbnails should zoom or focus on the useful detail.
