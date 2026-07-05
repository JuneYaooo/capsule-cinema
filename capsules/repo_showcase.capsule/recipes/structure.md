---
type: Video Recipe
title: Structure Recipe
description: Story structure, pacing, beats, and scene architecture.
stage: planning
domain: structure
profile: video.okf.capsule.v1
tags:
- structure
---

# Structure

## Rules

- Default to the local short silent route: 4-5 pages, 8-10 seconds total, no narration track, no burned subtitles.
- Each page should add one useful reason to keep watching. Choose the page order by the strongest one-glance value: result, hidden resource, old-way contrast, risk warning, proof number, demo shock, mechanism, or practical next step.
- Default subject count is one repo, one Skill, or one tool. If a video truly covers multiple Skills/modules/tools, reserve a small dedicated subject_paths area for 3-5 representative short paths, and keep the main title about the shared office task or result.
- The top badge identifies the exact object (`owner/repo` or a short Skill path); the title explains what the object helps the viewer do and why it is worth attention.
- The bottom fact card is one visible 4-5 行 chain, not a separate headline plus filler. `bottom_title` must be empty or omitted; if the renderer receives a non-empty `bottom_title`, preflight fails. Each visible line should read like one natural viewer decision and may combine scene/problem, special mechanism, evidence, result, boundary, or tradeoff in the order that makes the value most obvious. Keep each line complete enough to read naturally, and short enough to stay readable in a phone preview; longer lines are allowed when the contact sheet proves they fit.
- The last page is not a platform CTA. Use it for a concrete handoff such as what to ask the agent, what material to prepare, what output to expect, or where the project stops being suitable.
- Do not stretch a repo into a generic product tour. The structure must make the target viewer understand whether this project is worth trying, saving, or forwarding.
