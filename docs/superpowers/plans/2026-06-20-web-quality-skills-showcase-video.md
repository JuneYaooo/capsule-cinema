# Web Quality Skills Showcase Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a 3:4 short silent `github_skills_showcase` video for `addyosmani/web-quality-skills` without any visible links.

**Architecture:** Use the existing `github_skills_showcase` local-script capsule. Prepare source-grounded screenshot images and a compact JSON profile, render with the capsule script, then run visible-copy, video, and compliance QA before packaging the release.

**Tech Stack:** Python, PIL-based capsule renderer, ffmpeg/ffprobe, GitHub API/raw content, local QA scripts.

## Global Constraints

- Capsule: `github_skills_showcase`
- Route: short silent repo showcase
- Aspect ratio: 3:4
- Duration: 8-10 seconds
- Audio: packaged BGM only
- No voiceover
- No burned subtitles
- 4-5 visual cards
- Visible public materials must not contain URLs, domains, QR codes, or link prompts.
- Visible public materials must not contain the word `链接`.
- Visible public materials must not contain license claims such as `MIT` or `商用可用`.
- Visible public materials must not contain internal production words such as draft, source, revision, v1, real asset, or similar handoff language.
- Visible claims must not guarantee ranking, performance scores, accessibility compliance, or security outcomes.

---

### Task 1: Source Capture

**Files:**
- Create: `artifacts/video_runs/production/<run_slug>/inputs/source_materials/`
- Create: `artifacts/video_runs/production/<run_slug>/internal/source_notes.md`

**Interfaces:**
- Consumes: GitHub repository facts from `addyosmani/web-quality-skills`.
- Produces: Local screenshot PNGs with no visible URL/domain/link text.

- [ ] **Step 1: Create a run directory**

Run:

```bash
RUN_ROOT="artifacts/video_runs/production/$(date +%Y%m%d_%H%M%S)_web_quality_skills_showcase"
mkdir -p "$RUN_ROOT/inputs/source_materials" "$RUN_ROOT/internal" "$RUN_ROOT/qa"
```

Expected: directories exist under `$RUN_ROOT`.

- [ ] **Step 2: Capture source-grounded screenshots**

Create local PNG screenshots or rendered document crops for:

- README value proposition and skills table.
- Skills directory names.
- Codex setup usage lines without visible domains or URLs.
- A representative skill detail section if needed.

Expected: 4-5 PNG files in `$RUN_ROOT/inputs/source_materials/`.

- [ ] **Step 3: Check screenshots for visible links**

Inspect the generated images and use OCR/manual review where available.

Expected: no URL, domain, QR code, or `链接` visible in any source image.

### Task 2: Render Profile

**Files:**
- Create: `artifacts/video_runs/production/<run_slug>/inputs/repo_showcase_profile.json`
- Create: `artifacts/video_runs/production/<run_slug>/internal/audience_pull_card.md`
- Create: `artifacts/video_runs/production/<run_slug>/internal/value_card.md`

**Interfaces:**
- Consumes: source images from Task 1.
- Produces: JSON profile accepted by `render_repo_showcase_video.py`.

- [ ] **Step 1: Write internal audience and value cards**

Record the target audience, stop reason, care reason, user takeaway, source facts, and forbidden claims.

Expected: internal markdown files exist and are not copied into `public/`.

- [ ] **Step 2: Write the JSON profile**

Use the approved copy:

- Top title: `上线前先过这一关`
- Top subtitle: `网页质量别靠发布后补`
- Scene titles: `别等发布后才补`, `不是只跑个分数`, `6 个 Skill 分开管`, `改之前先有清单`, `把项目名发给 Agent`

Expected: profile has `voiceover_required=false`, `add_background_music=true`, `target_duration=10`, and 5 scenes with local `image_paths`.

- [ ] **Step 3: Preflight visible text**

Run:

```bash
python scripts/visible_copy_lint.py "$RUN_ROOT/qa/visible_text_for_preflight.txt" --json
```

Expected: lint returns success after writing the actual visible text file.

### Task 3: Capsule Render

**Files:**
- Create: `artifacts/video_runs/production/<run_slug>/release/video.mp4`
- Create: `artifacts/video_runs/production/<run_slug>/release/copy.txt`
- Create: `artifacts/video_runs/production/<run_slug>/artifact_manifest.json`

**Interfaces:**
- Consumes: profile from Task 2.
- Produces: capsule-rendered video and manifest.

- [ ] **Step 1: Run local capsule script**

Run:

```bash
python /Users/june2/.codex/video-production/capsule_assets/github_skills_showcase/script/render_repo_showcase_video.py \
  --topic "web-quality-skills" \
  --params "$RUN_ROOT/inputs/repo_showcase_profile.json" \
  --output-dir "$RUN_ROOT"
```

Expected: command exits 0 and writes `release/video.mp4`.

- [ ] **Step 2: Inspect artifact manifest**

Run:

```bash
python -m json.tool "$RUN_ROOT/artifact_manifest.json" >/dev/null
```

Expected: JSON is valid and includes the final video path.

### Task 4: QA And Release Package

**Files:**
- Create: `artifacts/video_runs/production/<run_slug>/qa/local_video_qa.json`
- Create: `artifacts/video_runs/production/<run_slug>/qa/compliance_review.md`
- Create: `artifacts/video_runs/production/web_quality_skills_showcase/release/<version_slug>/`
- Create: `artifacts/video_runs/production/web_quality_skills_showcase/CURRENT_RELEASE.md`

**Interfaces:**
- Consumes: rendered video and manifest from Task 3.
- Produces: publishable release package and QA reports.

- [ ] **Step 1: Run local video QA**

Run:

```bash
python scripts/local_video_qa.py \
  --run-dir "$RUN_ROOT" \
  --aspect-ratio "3:4" \
  --expect-audio \
  --output "$RUN_ROOT/qa/local_video_qa.json"
```

Expected: QA passes for duration, aspect ratio, and audio presence.

- [ ] **Step 2: Review frames for visible links**

Extract contact sheet or key frames and inspect visible text.

Expected: no URL, domain, QR code, or `链接` visible.

- [ ] **Step 3: Run self-media compliance review**

Review visible text, publishing copy, cover if present, and source claims.

Expected: no blocker or high-risk issue remains.

- [ ] **Step 4: Package release**

Copy final artifacts into a versioned release directory with `public/`, `qa/`, `technical/`, and `internal/`.

Expected: `CURRENT_RELEASE.md` points to the current approved release and `release_manifest.json` points to public assets and QA reports.
