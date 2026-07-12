# Five Underused Agent Skills Repo Showcases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce five approved 10-second Repo Show release packages, each recommending one verified Agent Skill with four real browser-captured source visuals.

**Architecture:** Reuse the active `repo_showcase` local renderer without changing application code. Store one self-contained production package per Skill under a shared batch root: researched facts and audience logic in `internal/`, browser screenshots and provenance in `inputs/`, the deterministic renderer output in `render/`, and final public/QA artifacts in `release/`.

**Tech Stack:** `agent-browser`, GitHub public pages/API, JSON/YAML, Python 3, Pillow, FFmpeg/ffprobe, the packaged Repo Show renderer, local QA and compliance scripts.

## Global Constraints

- Five subjects: `hallmark`, `extract-design-system`, `handoff`, `council`, and `firecrawl-research-papers` at the exact paths in the approved design.
- One concrete Skill per video; show its repository and short Skill path at phone-readable size.
- Output is 1080×1440 (3:4), fixed approximately 10 seconds, four scenes, silent except for the packaged `Manten Diloty` BGM.
- Each scene uses one approved actual browser screenshot with `actual_source: true`, `reconstructed_card: false`, and an allowed `actual_browser_*` capture method.
- Never substitute generated cards, local Markdown renders, copied/downloaded images, file-list-only screenshots, source-code screenshots, visible URLs, domains, QR codes, or link prompts.
- Do not use AI image/video generation, TTS, subtitles, generated music, lip sync, action transfer, or external media-generation providers.
- Do not claim universal safety, zero cost, commercial permission, autonomous task transfer, pixel-perfect copying, or guaranteed research correctness.
- A Skill with fewer than four useful approved browser captures is blocked and must not be rendered as an approved release.

---

### Task 1: Create the Batch Workspace and Evidence Cards

**Files:**
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/batch_manifest.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/internal/source_facts.json` and `audience_pull_card.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/extract-design-system/internal/source_facts.json` and `audience_pull_card.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/handoff/internal/source_facts.json` and `audience_pull_card.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/council/internal/source_facts.json` and `audience_pull_card.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/firecrawl-research-papers/internal/source_facts.json` and `audience_pull_card.json`

**Interfaces:**
- Consumes: the approved design and the five live GitHub `SKILL.md` files.
- Produces: one normalized subject record per Skill with `repo_slug`, `skill_name`, `skill_path`, `source_url`, `license`, `dependencies`, `claims`, `boundaries`, `primary_audience`, `stop_reason`, and `viewer_takeaway`.

- [ ] **Step 1: Create the shared directory layout**

Run:

```bash
mkdir -p artifacts/video_runs/production/20260712_underused_agent_skills_batch/{hallmark,extract-design-system,handoff,council,firecrawl-research-papers}/{inputs/source_materials,internal,render,release/public,release/technical,release/qa}
```

Expected: five Skill directories, each with inputs, internal, render, and release subdirectories.

- [ ] **Step 2: Verify live Skill identity and repository metadata**

Run the GitHub Contents API for these exact paths and record only facts present in the current files:

```text
Nutlope/hallmark/skills/hallmark/SKILL.md
arvindrk/extract-design-system/skills/extract-design-system/SKILL.md
mattpocock/skills/skills/productivity/handoff/SKILL.md
warpdotdev/common-skills/.agents/skills/council/SKILL.md
firecrawl/firecrawl-workflows/skills/firecrawl-research-papers/SKILL.md
```

Expected: every file begins with frontmatter whose `name` matches the selected Skill.

- [ ] **Step 3: Write source and audience cards**

For each subject, write `source_facts.json` and `audience_pull_card.json`. Every public claim must cite a current GitHub path or official page in an internal `evidence` field; dependencies and limitations must be explicit.

Expected: no unsupported superlatives, no hidden external dependency, and one concrete muted-video takeaway per subject.

- [ ] **Step 4: Write the batch manifest**

Write `batch_manifest.json` with the five subjects in the approved publication order and initial status `evidence_ready`.

Expected: `jq -e '.subjects | length == 5' batch_manifest.json` exits 0.

### Task 2: Capture and Validate Hallmark Prototype Material

**Files:**
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/source_materials/01_skill_identity.png`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/source_materials/02_modes.png`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/source_materials/03_structure.png`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/source_materials/04_safety_boundary.png`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/source_asset_manifest.json`

**Interfaces:**
- Consumes: Hallmark evidence cards from Task 1 and real browser-opened public pages.
- Produces: four existing PNG files and a renderer-compatible provenance manifest.

- [ ] **Step 1: Open and inspect the Hallmark GitHub and official Skill pages**

Use a dedicated `agent-browser` session. Capture only rendered content areas that show identity/purpose, operation modes, structural-variety guidance, and implementation/copyright safety boundaries.

Expected: screenshots contain useful rendered page evidence and no browser chrome, address bar, QR code, or visible full URL.

- [ ] **Step 2: Save four actual browser screenshots**

Use content-area or element screenshots. Do not download embedded images or locally render Markdown.

Expected: all PNGs are readable, nonblank, and visually different enough to advance four separate facts.

- [ ] **Step 3: Write the Hallmark source manifest**

Use four records with stable IDs `hallmark_01` through `hallmark_04`. Each record must contain:

```json
{
  "asset_id": "hallmark_01",
  "asset_type": "browser_evidence_screenshot",
  "source_kind": "github_skill_page",
  "source_url_or_repo_path": "Nutlope/hallmark/skills/hallmark/SKILL.md",
  "capture_method": "actual_browser_github_repo_readme_key_area_screenshot",
  "path": "/absolute/path/to/01_skill_identity.png",
  "reconstructed_card": false,
  "actual_source": true
}
```

Expected: all four absolute paths exist and all capture methods start with `actual_browser_`.

- [ ] **Step 4: Inspect the four screenshots**

Create a contact sheet or open them individually. Reject unreadable, redundant, URL-bearing, or file-list-only captures.

Expected: four approved images remain; otherwise recapture before proceeding.

### Task 3: Draft, Render, and Review the Hallmark Prototype

**Files:**
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/internal/title_candidates.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/viewer_facing_text.txt`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/repo_showcase_profile.json`
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/render/final_video.mp4`

**Interfaces:**
- Consumes: Hallmark facts, audience card, screenshots, and source manifest.
- Produces: a validated profile and the first prototype video whose layout becomes the batch baseline.

- [ ] **Step 1: Generate and score twelve Hallmark title candidates**

Cover result-first, comparison, mechanism, proof, and tradeoff angles. Select one title that explicitly connects Hallmark to reducing repetitive AI webpage structure.

Expected: the selected title fails if it can be reused unchanged for another Skill.

- [ ] **Step 2: Write four distinct fact-chain cards**

Each scene gets four or five complete Chinese lines. The sequence must advance from the recognizable design problem to Hallmark's modes, structural-variety mechanism, and a concrete human/copyright boundary.

Expected: no README-summary filler, URLs, production labels, generic engagement CTA, or unsupported quality guarantee.

- [ ] **Step 3: Run visible-copy lint before rendering**

Run the project viewer-facing copy lint against `viewer_facing_text.txt`.

Expected: exit 0 with no blocker hits.

- [ ] **Step 4: Write and validate the renderer profile**

Set `target_duration` to `10`, `width` to `1080`, `height` to `1440`, four scenes, packaged BGM, no speech/subtitles, exact Skill identity, and source asset IDs that match the manifest.

Run the existing Repo Show profile validation tests or direct preflight.

Expected: profile passes the active browser-only source contract.

- [ ] **Step 5: Render the Hallmark prototype**

Run:

```bash
python3 capsules/repo_showcase.capsule/scripts/render_repo_showcase_video.py \
  --topic hallmark_skill_showcase \
  --params artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/inputs/repo_showcase_profile.json \
  --output-dir artifacts/video_runs/production/20260712_underused_agent_skills_batch/hallmark/render
```

Expected: renderer exits 0 and writes a playable MP4 plus visible-text and manifest artifacts.

- [ ] **Step 6: Run technical and visual prototype checks**

Use `ffprobe`, local video QA, frame extraction/contact sheet, and direct image review.

Expected: 1080×1440, approximately 10 seconds, audio and video streams present, no black/frozen tail, no cropped title, and readable bottom cards.

### Task 4: Capture and Render the Remaining Four Skills

**Files:**
- Create under `artifacts/video_runs/production/20260712_underused_agent_skills_batch/extract-design-system/`: four numbered PNGs in `inputs/source_materials/`, `inputs/source_asset_manifest.json`, `inputs/viewer_facing_text.txt`, `inputs/repo_showcase_profile.json`, `internal/title_candidates.json`, and `render/final_video.mp4`.
- Create the same named artifact set under `artifacts/video_runs/production/20260712_underused_agent_skills_batch/handoff/`.
- Create the same named artifact set under `artifacts/video_runs/production/20260712_underused_agent_skills_batch/council/`.
- Create the same named artifact set under `artifacts/video_runs/production/20260712_underused_agent_skills_batch/firecrawl-research-papers/`.

**Interfaces:**
- Consumes: the approved Hallmark layout baseline and each Skill's own verified evidence.
- Produces: four additional individually validated videos without reusing Hallmark claims or screenshots.

- [ ] **Step 1: Capture four approved browser visuals per Skill**

Use each Skill's GitHub-rendered `SKILL.md`, referenced documentation, official CLI/demo page, dependency section, or relevant safety boundary. Keep each Skill's four screenshots distinct and source-grounded.

Expected: 16 approved screenshots and four valid provenance manifests.

- [ ] **Step 2: Draft and lint Skill-specific copy**

Use these required boundaries:

```text
extract-design-system: starter tokens, Playwright/Chromium, not a component library or pixel-perfect copy.
handoff: writes an artifact for a fresh Agent, not automatic transfer or execution.
council: requires subagent/model access and is excessive for simple decisions.
firecrawl-research-papers: requires FIRECRAWL_API_KEY/external service and source papers still need review.
```

Expected: four visible-copy lint passes.

- [ ] **Step 3: Write and preflight four renderer profiles**

Expected: each profile has exactly four scenes, exact Skill identity, `target_duration: 10`, packaged BGM, and four matching approved asset IDs.

- [ ] **Step 4: Render the four videos**

Run the same local renderer once per Skill with a dedicated output directory.

Expected: four renderer exit codes of 0 and four playable MP4 files.

- [ ] **Step 5: Run per-video technical and visual checks**

Expected: each video meets the same resolution, duration, stream, tail, readability, and source rules as the Hallmark prototype.

### Task 5: Package, Audit, and Publish the Batch Locally

**Files:**
- Create under each of the five exact Skill roots: `release/public/<skill-name>_repo_showcase.mp4`, `release/public/cover.jpg`, `release/public/publishing_copy.txt`, `release/technical/repo_showcase_profile.json`, `release/technical/source_asset_manifest.json`, `release/qa/local_video_qa.json`, `release/qa/compliance_review.md`, `release/release_manifest.json`, and `release/README.md`.
- Create: `artifacts/video_runs/production/20260712_underused_agent_skills_batch/batch_report.json`
- Modify: `CURRENT_RELEASE.md`

**Interfaces:**
- Consumes: five passing renderer outputs and their internal/technical evidence.
- Produces: five self-contained local release packages and one unambiguous batch pointer.

- [ ] **Step 1: Copy only approved public artifacts into each release**

Public directories contain only the final MP4, cover, and viewer-facing publishing copy. Planning language and source URLs remain in internal/technical files.

Expected: no draft/version/source terminology leaks into public files.

- [ ] **Step 2: Run local video QA for all five releases**

Expected: five QA reports with no blocker for format, duration, streams, black frames, frozen tail, or artifact accessibility.

- [ ] **Step 3: Run self-media compliance review for all five packages**

Audit video text, cover, title, publishing copy, links, licensing language, security claims, and external-service dependencies.

Expected: no unresolved Blocker or unaccepted High finding.

- [ ] **Step 4: Validate release manifests and checksums**

Each manifest identifies the final video, cover, publishing copy, QA report, compliance report, lint result, source repository, exact Skill path, and file hashes.

Expected: every referenced path exists and hashes match.

- [ ] **Step 5: Write the batch report and current-release pointer**

Record successes, blocked Skills, final paths, durations, resolution, QA status, and compliance status. Update `CURRENT_RELEASE.md` to point to the batch root and explicitly identify the five current public videos.

Expected: the user can find every final video without inferring versions from filenames.

- [ ] **Step 6: Run the final verification command set**

Run `python3 -m unittest tests.python.test_repo_showcase_capsule`, the project visible-copy lint for each viewer text file, local video QA for each MP4, release-manifest validation for each package, and `ffprobe` stream/duration checks against all five delivered files.

Expected: five release-ready videos, or an explicit batch report that names any blocked Skill and the exact unmet source/QA gate.
