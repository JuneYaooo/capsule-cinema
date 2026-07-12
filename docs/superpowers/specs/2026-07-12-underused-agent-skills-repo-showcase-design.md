# Five Underused Agent Skills Repo Showcases

## Goal

Produce five independent, release-ready Repo Show videos about concrete Agent Skills that solve recognizable problems without repeating the common PPT/PDF/XLSX recommendation lane.

Each video covers exactly one Skill:

1. `Nutlope/hallmark` — `skills/hallmark`
2. `arvindrk/extract-design-system` — `skills/extract-design-system`
3. `mattpocock/skills` — `skills/productivity/handoff`
4. `warpdotdev/common-skills` — `.agents/skills/council`
5. `firecrawl/firecrawl-workflows` — `skills/firecrawl-research-papers`

The shared editorial idea is: five concrete Skills that repair common Agent weaknesses. The public videos do not claim that the set is exhaustive, universally safe, or commercially free.

## Audience And Success Criteria

Primary audience:

- Codex, Claude Code, Cursor, Gemini CLI, and other Agent users;
- developers and designers already seeing unreliable or generic Agent output;
- researchers and operators who need traceable handoffs, decisions, design systems, or sources.

Each muted 10-second video must let a phone viewer answer:

- what exact Skill is shown;
- what user problem it solves;
- what mechanism makes it different from a generic prompt;
- what dependency or limitation matters before installation.

## Format

Use the active `repo_showcase` capsule without changing its release contract:

- 3:4 vertical video;
- fixed 10-second duration;
- 4–5 pages, with four approved browser-captured middle visuals;
- packaged `Manten Diloty` BGM only;
- no narration, TTS, subtitles, generated imagery, or source audio;
- dark-grid Repo Show renderer;
- exact repository and short Skill path visible on a phone;
- one Skill per video.

No new renderer behavior is required. Profiles and copy are specific to a Skill while browser evidence remains traceable to its source repository and relevant public pages.

## Editorial Angles

### Hallmark

- User problem: generated websites repeat recognizable AI layout and styling defaults.
- Mechanism: design, audit, redesign, and study modes; structural variety rather than color swapping.
- Boundary: it encodes an opinionated design approach and cannot replace human taste or authorize copying protected brand assets.

### Extract Design System

- User problem: an Agent sees a reference website but guesses its design primitives inconsistently.
- Mechanism: extracts public-site colors, typography, spacing, radius, and shadows into starter JSON/CSS tokens.
- Boundary: requires Playwright/Chromium; produces starter tokens rather than a component library or pixel-perfect copy.

### Handoff

- User problem: a fresh Agent session lacks the working context of a long conversation.
- Mechanism: writes a compact handoff, references existing artifacts, suggests relevant Skills, and redacts sensitive data.
- Boundary: it prepares the handoff document; it does not automatically transfer or execute the task in another Agent.

### Council

- User problem: one model can anchor on its first explanation for a risky decision.
- Mechanism: model-diverse subagents investigate independently, compare findings, and synthesize a recommendation.
- Boundary: requires a runtime with subagent/model access and is wasteful for simple questions.

### Firecrawl Research Papers

- User problem: generic research output may lack paper discovery, related-paper expansion, and in-body verification.
- Mechanism: a constrained literature-review workflow across papers, PDFs, whitepapers, and technical reports.
- Boundary: requires `FIRECRAWL_API_KEY`, depends on an external service, and does not replace reading source papers.

## Source And Visual Plan

Every approved middle image must be captured from an actual browser-opened GitHub, Skills, documentation, demo, or official project page. Every scene mapping must use an approved `actual_browser_*` capture method, an existing local file, `actual_source: true`, and `reconstructed_card: false`.

For each Skill, capture four complementary views where available:

1. rendered `SKILL.md` identity and purpose;
2. the distinctive workflow or mode section;
3. supporting references, scripts, output contract, or official demo evidence;
4. dependency, security, installation, or limitation evidence.

Do not approve local Markdown renders, generated cards, copied repository images, downloaded screenshots, file-list-only views, visible URLs, domains, QR codes, or generic source code screenshots. If a Skill cannot supply four useful approved browser captures, mark that release blocked and do not substitute fabricated material.

## Copy And Hook Contract

Generate at least twelve internal title candidates per Skill across result-first, old-way comparison, mechanism, proof, and tradeoff angles. Select the final title using project specificity, immediate user value, evidence, muted readability, and the non-replaceable test.

Viewer-facing copy must:

- name a concrete task, input, output, or failure avoided;
- identify the exact Skill rather than only the parent repository;
- derive its claims from the `SKILL.md`, referenced files, official pages, or directly visible evidence;
- use four or five complete bottom-card lines;
- end with a practical decision or boundary rather than a generic engagement CTA;
- avoid production terminology, URLs, license promises, ranking claims, and unsupported safety claims.

## Production And Release Flow

1. Refresh repository metadata and read the complete current Skill source.
2. Build the propagation and audience cards internally.
3. Capture and provenance-map four approved browser visuals per Skill.
4. Draft and lint viewer-facing copy.
5. Render five separate Repo Show profiles with the packaged BGM.
6. Run technical video QA, contact-sheet visual review, copy lint, artifact validation, and self-media compliance review.
7. Package each approved video under a dedicated release directory with `public/`, `internal/`, `technical/`, `qa/`, and `release_manifest.json`.
8. Update `CURRENT_RELEASE.md` only after all five intended release pointers are unambiguous.

## Tool Chain

- Source research and capture: real browser automation against public pages.
- Rendering and compositing: `capsules/repo_showcase.capsule/scripts/render_repo_showcase_video.py` and local FFmpeg/Pillow dependencies used by the capsule.
- Audio: packaged `capsules/repo_showcase.capsule/assets/manten_diloty_bgm_cut_37sec.mp3`.
- Copy lint: the project viewer-facing copy lint path.
- QA: local video QA, capsule release gates, contact sheets, artifact validation, and final self-media compliance review.
- Explicitly unused: image generation, video generation, TTS, generated music, lip sync, action transfer, and external media-generation providers.

## Failure Handling

- Missing four approved browser visuals: block that Skill; do not downgrade to generated or downloaded imagery.
- Inaccessible source page: retry the same approved browser route or use another official/public page allowed by the capsule.
- Unsupported or ambiguous claim: remove or soften it before rendering.
- External dependency unavailable: state the dependency as a boundary; do not imply a completed live integration test.
- QA or compliance blocker: keep the release internal until corrected and rechecked.

## Verification

Completion requires five playable 3:4 videos with valid audio/video streams, duration within the capsule tolerance around 10 seconds, no black/frozen tail, readable phone-scale text, four approved provenance-mapped visuals per video, passing visible-copy lint, release manifests, local QA reports, and compliance reports with no unresolved blocker or unaccepted high-risk finding.
