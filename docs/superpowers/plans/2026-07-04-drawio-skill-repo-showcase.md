# drawio-skill Repo Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a default `repo_showcase` 3:4 silent video release package for `Agents365-ai/drawio-skill`.

**Architecture:** Use the existing `repo_showcase.capsule` local-script renderer. The work is a production run, not a renderer change: audit source facts and real visual assets, create a profile JSON, render with packaged BGM, then package QA, compliance, publishing copy, and release metadata.

**Tech Stack:** Python 3, Pillow renderer in `capsules/repo_showcase.capsule/scripts/render_repo_showcase_video.py`, ffmpeg/ffprobe, `scripts/visible_copy_lint.py`, `scripts/local_video_qa.py`, markdown/JSON release artifacts.

## Global Constraints

- Capsule route: `short_silent_repo_showcase`
- Aspect ratio: 3:4, 1080 x 1440
- Duration: 8-10 seconds
- Scene count: 5
- Audio: packaged Manten Diloty BGM only
- Voiceover: none
- Burned subtitles: none
- Identity badge: `Agents365-ai/drawio-skill`
- Use real repository assets or README rendered-content screenshots for at least four middle visuals.
- Do not show full URLs, domains, QR codes, "source", "draft", "v1", or production/revision language in viewer-facing copy.
- Do not promise fully automatic architecture correctness.
- Final package must include public, qa, technical, and internal artifacts plus `CURRENT_RELEASE.md` and `release_manifest.json`.

---

## File Structure

- Create: `output/drawio-skill-repo-showcase/inputs/repo_showcase_profile.json`
  - Renderer profile containing all visible card text, scene timings, source image paths, and BGM settings.
- Create: `output/drawio-skill-repo-showcase/inputs/source_asset_manifest.json`
  - Provenance for every middle visual.
- Create: `output/drawio-skill-repo-showcase/inputs/source_assets/*`
  - Real repo visual assets downloaded from the project or rendered README/source screenshots.
- Create: `output/drawio-skill-repo-showcase/internal/*`
  - Audience pull card, user-first brief, hook/title bakeoff, fact boundary map, and storyboard notes.
- Create: `output/drawio-skill-repo-showcase/public/*`
  - Final video, viewer-facing copy, and platform copy mirrored from release outputs.
- Create: `output/drawio-skill-repo-showcase/qa/*`
  - Visible lint report, local video QA, contact sheets, compliance review, and public copy lint.
- Create: `output/drawio-skill-repo-showcase/technical/*`
  - ffprobe output, render notes, source asset manifest copy, and source audit notes.
- Create: `output/drawio-skill-repo-showcase/release/release_manifest.json`
  - Final release manifest pointing to video, copy, QA, compliance, and platform copy artifacts.
- Create: `output/drawio-skill-repo-showcase/CURRENT_RELEASE.md`
  - Pointer to the current release and publishing-ready artifacts.

## Task 1: Source Audit And Asset Intake

**Files:**
- Create: `output/drawio-skill-repo-showcase/inputs/source_assets/`
- Create: `output/drawio-skill-repo-showcase/technical/source_audit.md`
- Create: `output/drawio-skill-repo-showcase/inputs/source_asset_manifest.json`

**Interfaces:**
- Consumes: design spec at `docs/superpowers/specs/2026-07-04-drawio-skill-repo-showcase-design.md`
- Produces: local image paths consumed by `repo_showcase_profile.json`

- [ ] **Step 1: Create output directories**

Run:

```bash
mkdir -p output/drawio-skill-repo-showcase/{inputs/source_assets,internal,public,qa,technical,release,publish}
```

Expected: exit 0.

- [ ] **Step 2: Download README and real visual assets**

Run:

```bash
curl -L --retry 3 --max-time 60 \
  https://raw.githubusercontent.com/Agents365-ai/drawio-skill/main/README.md \
  -o output/drawio-skill-repo-showcase/technical/source_readme.md
curl -L --retry 3 --max-time 60 \
  https://raw.githubusercontent.com/Agents365-ai/drawio-skill/main/assets/microservices-example.png \
  -o output/drawio-skill-repo-showcase/inputs/source_assets/microservices-example.png
curl -L --retry 3 --max-time 60 \
  https://raw.githubusercontent.com/Agents365-ai/drawio-skill/main/assets/demo-layered.png \
  -o output/drawio-skill-repo-showcase/inputs/source_assets/demo-layered.png
curl -L --retry 3 --max-time 60 \
  https://raw.githubusercontent.com/Agents365-ai/drawio-skill/main/assets/code-structure-example.png \
  -o output/drawio-skill-repo-showcase/inputs/source_assets/code-structure-example.png
```

Expected: files exist and are non-empty.

- [ ] **Step 3: Create source screenshots if needed**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path("output/drawio-skill-repo-showcase")
assets = root / "inputs" / "source_assets"
readme = (root / "technical" / "source_readme.md").read_text(encoding="utf-8")

sections = [
    ("readme_highlights.png", "README highlights", "## ✨ Highlights", "## 🖼️ Examples"),
    ("readme_visualize_code.png", "Code and infrastructure inputs", "## 🗺️ Visualize Code & Infrastructure", "| Piece | What it does |"),
    ("readme_install_skill.png", "Install and quick start", "## 🚀 Installation", "## ⚡ Quick Start"),
]

font_candidates = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
font_path = next((p for p in font_candidates if Path(p).exists()), None)
body_font = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
title_font = ImageFont.truetype(font_path, 34) if font_path else ImageFont.load_default()

def sanitize(line: str) -> str:
    line = line.replace("https://", "").replace("http://", "")
    line = line.replace("github.com/", "")
    line = line.replace("agents365-ai.github.io/", "")
    line = line.replace("skillsmp.com/", "")
    line = line.replace("clawhub.ai/", "")
    return line[:92]

def wrap(line: str, limit: int = 78):
    if len(line) <= limit:
        return [line]
    chunks = []
    while len(line) > limit:
        chunks.append(line[:limit])
        line = line[limit:]
    if line:
        chunks.append(line)
    return chunks

for filename, title, start, end in sections:
    start_idx = readme.find(start)
    end_idx = readme.find(end, start_idx + 1) if start_idx >= 0 else -1
    excerpt = readme[start_idx:end_idx if end_idx > start_idx else start_idx + 2200]
    lines = []
    for raw in excerpt.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("<") or raw.startswith("[!") or raw.startswith("```"):
            continue
        if "http" in raw or "github.com" in raw or raw.startswith("[!["):
            continue
        clean = sanitize(raw.replace("**", "").replace("`", ""))
        if clean:
            lines.extend(wrap(clean))
        if len(lines) >= 16:
            break

    im = Image.new("RGB", (1200, 760), "#F8FAFC")
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((36, 36, 1164, 724), radius=24, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((72, 68), title, fill="#0F172A", font=title_font)
    y = 126
    for line in lines:
        draw.text((78, y), line, fill="#1E293B", font=body_font)
        y += 38
    im.save(assets / filename)
PY
```

Expected: three fallback screenshots exist. These are source-derived README content images, not fake project output.

- [ ] **Step 4: Write source audit and manifest**

Create `output/drawio-skill-repo-showcase/technical/source_audit.md` and `output/drawio-skill-repo-showcase/inputs/source_asset_manifest.json` with exact provenance for each asset.

Expected: manifest has at least five entries and at least four entries have `"actual_source_first": true`.

## Task 2: Copy, Storyboard, And Profile

**Files:**
- Create: `output/drawio-skill-repo-showcase/internal/audience_pull_card.md`
- Create: `output/drawio-skill-repo-showcase/internal/user_first_brief.md`
- Create: `output/drawio-skill-repo-showcase/internal/hook_title_bakeoff.md`
- Create: `output/drawio-skill-repo-showcase/internal/fact_boundary_map.md`
- Create: `output/drawio-skill-repo-showcase/inputs/repo_showcase_profile.json`

**Interfaces:**
- Consumes: `source_asset_manifest.json`
- Produces: renderer-ready profile JSON

- [ ] **Step 1: Write internal audience and hook notes**

Create internal markdown files covering primary audience, current alternative, stop reason, use reason, actionable takeaway, wrong audience, 12 title candidates, selected title, and fact-to-source boundaries.

Expected: files are internal only and do not need to be viewer-facing.

- [ ] **Step 2: Write profile JSON**

Create `output/drawio-skill-repo-showcase/inputs/repo_showcase_profile.json` with:

- `repo_slug`: `Agents365-ai/drawio-skill`
- `tag`: `Agents365-ai/drawio-skill`
- `target_duration`: `10`
- `production_mode`: `short_silent_repo_showcase`
- `top_title`: `5k 星 draw.io Skill\n把架构画成可编辑图`
- `top_subtitle`: `自然语言、代码库、IaC、SQL、Mermaid 都能进 draw.io`
- `scenes`: five 2-second scenes with 4-5 bottom lines each.

Expected: no `voiceover`, `narration`, `tts_text`, or `speech_text` fields.

- [ ] **Step 3: Pre-render visible copy lint**

Run:

```bash
python scripts/visible_copy_lint.py \
  output/drawio-skill-repo-showcase/inputs/repo_showcase_profile.json \
  --json > output/drawio-skill-repo-showcase/qa/profile_visible_copy_lint.json
```

Expected: exit 0.

## Task 3: Render Video

**Files:**
- Create: `output/drawio-skill-repo-showcase/release/video.mp4`
- Create: `output/drawio-skill-repo-showcase/release/copy.txt`
- Create: `output/drawio-skill-repo-showcase/qa/run_notes.json`
- Create: `output/drawio-skill-repo-showcase/artifact_manifest.json`

**Interfaces:**
- Consumes: `repo_showcase_profile.json`
- Produces: final rendered video and renderer manifest

- [ ] **Step 1: Run renderer**

Run:

```bash
python capsules/repo_showcase.capsule/scripts/render_repo_showcase_video.py \
  --topic drawio-skill-repo-showcase \
  --params output/drawio-skill-repo-showcase/inputs/repo_showcase_profile.json \
  --output-dir output/drawio-skill-repo-showcase
```

Expected: exit 0 and `output/drawio-skill-repo-showcase/release/video.mp4` exists.

- [ ] **Step 2: Confirm technical properties**

Run:

```bash
ffprobe -v error -show_entries stream=codec_type,width,height -show_entries format=duration \
  -of json output/drawio-skill-repo-showcase/release/video.mp4 \
  > output/drawio-skill-repo-showcase/technical/ffprobe.json
```

Expected: duration is 8-10 seconds, video dimensions are 1080 x 1440, and one audio stream exists.

## Task 4: QA, Contact Sheets, And Compliance

**Files:**
- Create: `output/drawio-skill-repo-showcase/qa/local_video_qa.json`
- Create: `output/drawio-skill-repo-showcase/qa/final_contact_sheet.jpg`
- Create: `output/drawio-skill-repo-showcase/qa/source_assets_contact_sheet.jpg`
- Create: `output/drawio-skill-repo-showcase/qa/compliance_review.md`

**Interfaces:**
- Consumes: `release/video.mp4`, source assets, visible copy reports
- Produces: QA evidence for release manifest

- [ ] **Step 1: Run local video QA**

Run:

```bash
python scripts/local_video_qa.py \
  --run-dir output/drawio-skill-repo-showcase \
  --final-video output/drawio-skill-repo-showcase/release/video.mp4 \
  --aspect-ratio 3:4 \
  --min-duration 8 \
  --expect-audio \
  --require-prompts \
  --json \
  --output output/drawio-skill-repo-showcase/qa/local_video_qa.json
```

Expected: exit 0.

- [ ] **Step 2: Generate contact sheets**

Run:

```bash
ffmpeg -y -i output/drawio-skill-repo-showcase/release/video.mp4 \
  -vf "fps=1,scale=270:-1,tile=5x2" -frames:v 1 \
  output/drawio-skill-repo-showcase/qa/final_contact_sheet.jpg
python3 - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json

root = Path("output/drawio-skill-repo-showcase")
manifest = json.loads((root / "inputs" / "source_asset_manifest.json").read_text(encoding="utf-8"))
items = manifest if isinstance(manifest, list) else manifest.get("assets", [])
thumbs = []
for item in items:
    p = Path(item["path"])
    im = ImageOps.exif_transpose(Image.open(p).convert("RGB"))
    im.thumbnail((320, 210))
    canvas = Image.new("RGB", (340, 270), "#F8FAFC")
    canvas.paste(im, ((340 - im.width)//2, 12))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 226), item["asset_id"][:36], fill="#0F172A")
    draw.text((12, 246), item["source_kind"][:42], fill="#475569")
    thumbs.append(canvas)

sheet = Image.new("RGB", (680, 270 * ((len(thumbs)+1)//2)), "#E2E8F0")
for idx, thumb in enumerate(thumbs):
    x = (idx % 2) * 340
    y = (idx // 2) * 270
    sheet.paste(thumb, (x, y))
sheet.save(root / "qa" / "source_assets_contact_sheet.jpg")
PY
```

Expected: both contact sheets exist.

- [ ] **Step 3: Write compliance review**

Create `output/drawio-skill-repo-showcase/qa/compliance_review.md` with conclusion `Low`, no blocker, no unresolved high risk, and notes on source-material and BGM authorization.

Expected: report includes release text, visible frame text, source material, and publishing copy scope.

## Task 5: Publishing Package And Release Package

**Files:**
- Create: `output/drawio-skill-repo-showcase/release/publishing_package.md`
- Create: `output/drawio-skill-repo-showcase/publish/wechat_channels.md`
- Create: `output/drawio-skill-repo-showcase/publish/douyin.md`
- Create: `output/drawio-skill-repo-showcase/publish/xiaohongshu.md`
- Create: `output/drawio-skill-repo-showcase/publish/bilibili.md`
- Create: `output/drawio-skill-repo-showcase/publish/kuaishou.md`
- Create: `output/drawio-skill-repo-showcase/publish/platform_copy_manifest.json`
- Create: `output/drawio-skill-repo-showcase/release/release_manifest.json`
- Create: `output/drawio-skill-repo-showcase/CURRENT_RELEASE.md`

**Interfaces:**
- Consumes: final video, QA artifacts, compliance review
- Produces: publishing-ready release directory

- [ ] **Step 1: Write platform copy**

Create the publishing package and platform-specific files. The recommended title should be:

```text
5k 星 draw.io Skill：把仓库和架构画成可编辑图
```

Expected: copy includes boundary that diagrams still need human review.

- [ ] **Step 2: Lint public copy**

Run:

```bash
python scripts/visible_copy_lint.py \
  output/drawio-skill-repo-showcase/release/publishing_package.md \
  output/drawio-skill-repo-showcase/publish/*.md \
  --json > output/drawio-skill-repo-showcase/qa/public_copy_lint.json
```

Expected: exit 0.

- [ ] **Step 3: Copy publishing assets into public**

Run:

```bash
cp output/drawio-skill-repo-showcase/release/video.mp4 output/drawio-skill-repo-showcase/public/video.mp4
cp output/drawio-skill-repo-showcase/release/copy.txt output/drawio-skill-repo-showcase/public/copy.txt
cp output/drawio-skill-repo-showcase/release/publishing_package.md output/drawio-skill-repo-showcase/public/publishing_package.md
cp output/drawio-skill-repo-showcase/publish/platform_copy_manifest.json output/drawio-skill-repo-showcase/public/platform_copy_manifest.json
```

Expected: public directory contains only publishing-ready assets.

- [ ] **Step 4: Write release manifest and current pointer**

Create `release/release_manifest.json` with paths to final video, copy, publishing package, platform copy manifest, QA report, visible copy lint, public copy lint, compliance review, contact sheets, source asset manifest, source URL, repo slug, capsule name, toolchain, created_at, and supersedes.

Create `CURRENT_RELEASE.md` pointing to the current release artifacts.

Expected: release package is discoverable without guessing from old versions.

## Task 6: Final Verification

**Files:**
- Read: `output/drawio-skill-repo-showcase/release/release_manifest.json`
- Read: `output/drawio-skill-repo-showcase/qa/local_video_qa.json`
- Read: `output/drawio-skill-repo-showcase/qa/visible_copy_lint.json`
- Read: `output/drawio-skill-repo-showcase/qa/public_copy_lint.json`
- Read: `output/drawio-skill-repo-showcase/qa/compliance_review.md`

**Interfaces:**
- Consumes: all release and QA artifacts
- Produces: final report to user

- [ ] **Step 1: Verify final requirements**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("output/drawio-skill-repo-showcase")
required = [
    root / "release" / "video.mp4",
    root / "release" / "publishing_package.md",
    root / "release" / "release_manifest.json",
    root / "CURRENT_RELEASE.md",
    root / "qa" / "local_video_qa.json",
    root / "qa" / "visible_copy_lint.json",
    root / "qa" / "public_copy_lint.json",
    root / "qa" / "compliance_review.md",
    root / "qa" / "final_contact_sheet.jpg",
    root / "qa" / "source_assets_contact_sheet.jpg",
    root / "inputs" / "source_asset_manifest.json",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit("missing artifacts: " + ", ".join(missing))
qa = json.loads((root / "qa" / "local_video_qa.json").read_text(encoding="utf-8"))
visible = json.loads((root / "qa" / "visible_copy_lint.json").read_text(encoding="utf-8"))
public = json.loads((root / "qa" / "public_copy_lint.json").read_text(encoding="utf-8"))
print(json.dumps({
    "missing": missing,
    "local_video_qa_keys": sorted(qa.keys()),
    "visible_copy_lint": visible,
    "public_copy_lint": public,
}, ensure_ascii=False, indent=2))
PY
```

Expected: no missing artifacts and lint reports indicate success.

- [ ] **Step 2: Report deliverables**

Report final video path, release manifest path, QA path, compliance path, and any residual risks such as BGM/source-material authorization needing publisher-side retention.

Expected: user can play the final video and publish from `public/`.

