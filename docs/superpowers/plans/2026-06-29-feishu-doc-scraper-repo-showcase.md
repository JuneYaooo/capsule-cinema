# Feishu Doc Scraper Repo Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a 3:4 silent `repo_showcase` video for the `feishu-doc-scraper` skill, with source-grounded visuals, Chinese office-productivity copy, BGM, and QA artifacts.

**Architecture:** Use the existing `repo_showcase` local-script capsule renderer without modifying renderer code. Prepare real source screenshots and a source manifest from the local `feishu-doc-scraper` skill file, pass a compact profile JSON to the renderer, then package the renderer outputs into a release directory with QA reports.

**Tech Stack:** Python 3, Pillow, ffmpeg/ffprobe, existing `repo_showcase` renderer at `/Users/june2/.codex/video-production/capsule_assets/repo_showcase/script/render_repo_showcase_video.py`, existing Capsule Cinema QA scripts.

## Global Constraints

- Capsule: `repo_showcase`
- Format: 3:4, 1080x1440
- Duration: about 10 seconds
- Scenes: 5
- Audio: packaged BGM only
- Voiceover: none
- Subtitles: none
- Public CTA inside video: none
- Source material must come from `/Users/june2/code/github/skills_meterial/office-productivity-skills/skills/office-documents/daymade_claude-code-skills__feishu-doc-scraper/SKILL.md` or direct references under that skill directory.
- No generated concept art, stock images, AI summary cards, browser chrome, URLs, QR codes, or visible links in public video frames.
- Visible copy must avoid "商用可用", "MIT", URLs, links, QR-code language, internal production terms, and permission-bypass claims.
- Final delivery must include final video, copywriting, source-asset manifest, visible text lint report, local video QA report, and run notes.

---

## File Structure

- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/`
  - Stores five real source screenshots generated from local `SKILL.md` snippets.
- Create: `output/feishu_doc_scraper_repo_showcase/inputs/source_asset_manifest.json`
  - Lists every middle-panel visual source with source file, line range, and asset type.
- Create: `output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json`
  - Profile consumed by the `repo_showcase` renderer.
- Create: `output/feishu_doc_scraper_repo_showcase/render/`
  - Raw renderer output directory containing `release/video.mp4`, `release/copy.txt`, `qa/`, `work/`, and `artifact_manifest.json`.
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/`
  - Final release package with `public/`, `qa/`, `technical/`, and `internal/`.
- Modify: none in source code.
- Test: existing renderer and QA scripts are invoked directly; no repo code changes require unit tests.

## Task 1: Build Source Screenshots And Manifest

**Files:**
- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/01-scope.png`
- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/02-api-path.png`
- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/03-recursion.png`
- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/04-permission-boundary.png`
- Create: `output/feishu_doc_scraper_repo_showcase/work/source_screenshots/05-acceptance.png`
- Create: `output/feishu_doc_scraper_repo_showcase/inputs/source_asset_manifest.json`

**Interfaces:**
- Consumes: local source file path `/Users/june2/code/github/skills_meterial/office-productivity-skills/skills/office-documents/daymade_claude-code-skills__feishu-doc-scraper/SKILL.md`
- Produces: PNG screenshot paths and `source_asset_manifest.json` entries used by Task 2 profile scenes.

- [ ] **Step 1: Create output directories**

```bash
mkdir -p \
  output/feishu_doc_scraper_repo_showcase/work/source_screenshots \
  output/feishu_doc_scraper_repo_showcase/inputs
```

- [ ] **Step 2: Generate source-content screenshots**

Run this from `/Users/june2/code/github/capsule-cinema`:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

source = Path("/Users/june2/code/github/skills_meterial/office-productivity-skills/skills/office-documents/daymade_claude-code-skills__feishu-doc-scraper/SKILL.md")
out_dir = Path("output/feishu_doc_scraper_repo_showcase/work/source_screenshots")
out_dir.mkdir(parents=True, exist_ok=True)

regular_candidates = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
bold_candidates = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

def font(size, bold=False):
    for candidate in bold_candidates if bold else regular_candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)

lines = source.read_text(encoding="utf-8").splitlines()

shots = [
    {
        "id": "01-scope",
        "title": "Scope: faithful Markdown",
        "line_start": 10,
        "line_end": 22,
        "asset_type": "github_source_file_screenshot",
        "caption": "Skill scope and route decision",
    },
    {
        "id": "02-api-path",
        "title": "Path A: lark-cli API",
        "line_start": 37,
        "line_end": 74,
        "asset_type": "github_source_file_screenshot",
        "caption": "Programmatic extraction path",
    },
    {
        "id": "03-recursion",
        "title": "Reference graph recursion",
        "line_start": 76,
        "line_end": 91,
        "asset_type": "github_source_file_screenshot",
        "caption": "Follow referenced docs and sheets",
    },
    {
        "id": "04-permission-boundary",
        "title": "Permission boundary",
        "line_start": 96,
        "line_end": 103,
        "asset_type": "github_source_file_screenshot",
        "caption": "Permission denied is explicit",
    },
    {
        "id": "05-acceptance",
        "title": "Acceptance contract",
        "line_start": 130,
        "line_end": 147,
        "asset_type": "github_source_file_screenshot",
        "caption": "Completion checks and gap reporting",
    },
]

manifest = []
for shot in shots:
    selected = lines[shot["line_start"] - 1:shot["line_end"]]
    W, H = 1400, 860
    img = Image.new("RGB", (W, H), "#f7f4e8")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((26, 26, W - 26, H - 26), radius=32, fill="#fffdf6", outline="#20A6B8", width=4)
    draw.text((64, 52), shot["title"], font=font(38, True), fill="#101820")
    draw.text((64, 104), "feishu-doc-scraper / SKILL.md", font=font(24, True), fill="#3c5964")
    y = 156
    code_font = font(24, False)
    line_no_font = font(21, False)
    for offset, text in enumerate(selected):
        if y > H - 56:
            break
        line_no = str(shot["line_start"] + offset).rjust(3)
        draw.text((64, y), line_no, font=line_no_font, fill="#7f8c8d")
        clipped = text[:84]
        color = "#0f1720"
        if clipped.startswith("##") or clipped.startswith("#"):
            color = "#0f7d8a"
        elif clipped.strip().startswith("```"):
            color = "#b26a00"
        elif "lark-cli" in clipped or "jq" in clipped or "pandoc" in clipped:
            color = "#7b2cbf"
        draw.text((126, y), clipped, font=code_font, fill=color)
        y += 32
    output = out_dir / f"{shot['id']}.png"
    img.save(output, quality=95)
    manifest.append({
        "asset_id": shot["id"],
        "path": str(output.resolve()),
        "asset_type": shot["asset_type"],
        "source_kind": "local_skill_file",
        "source_url_or_repo_path": str(source),
        "line_start": shot["line_start"],
        "line_end": shot["line_end"],
        "capture_method": "local PIL screenshot from exact source lines",
        "reconstructed_card": False,
        "caption": shot["caption"],
    })

manifest_path = Path("output/feishu_doc_scraper_repo_showcase/inputs/source_asset_manifest.json")
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(manifest_path)
for item in manifest:
    print(item["path"])
PY
```

Expected: command exits `0`, prints the manifest path plus five PNG paths.

- [ ] **Step 3: Verify manifest has five real-source entries**

```bash
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("output/feishu_doc_scraper_repo_showcase/inputs/source_asset_manifest.json").read_text(encoding="utf-8"))
assert len(manifest) == 5, len(manifest)
for item in manifest:
    assert Path(item["path"]).is_file(), item["path"]
    assert item["asset_type"] == "github_source_file_screenshot", item
    assert item["reconstructed_card"] is False, item
print("source manifest ok")
PY
```

Expected: `source manifest ok`.

## Task 2: Create Repo Showcase Profile

**Files:**
- Create: `output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json`

**Interfaces:**
- Consumes: five PNG paths and source manifest from Task 1.
- Produces: renderer profile JSON consumed by Task 3 via `--params`.

- [ ] **Step 1: Write profile JSON**

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("output/feishu_doc_scraper_repo_showcase")
shots = root / "work/source_screenshots"
manifest = json.loads((root / "inputs/source_asset_manifest.json").read_text(encoding="utf-8"))

profile = {
    "topic": "feishu-doc-scraper",
    "project_name": "feishu-doc-scraper",
    "top_title": "飞书文档，别再手动复制了",
    "top_subtitle": "Agent Skill / 飞书到本地 Markdown",
    "target_duration": 10,
    "scene_count": 5,
    "aspect_ratio": "3:4",
    "width": 1080,
    "height": 1440,
    "show_top_tag": False,
    "show_middle_title": True,
    "animate_middle": True,
    "image_mode": "auto_source",
    "bgm_volume": 0.72,
    "add_background_music": True,
    "copy": "\n".join([
        "标题：飞书文档，别再手动复制了",
        "",
        "正文：",
        "飞书文档、Wiki、表格、妙记一多，最怕的是复制漏段、引用漏页、会议转写又被二次改写。",
        "这个 feishu-doc-scraper Skill 的思路很硬：优先走 lark-cli API，把正文忠实落成本地 Markdown；合集继续追引用；权限不够就明确列出来。",
        "适合做团队资料归档、知识库迁移、会议纪要沉淀。下一条可以单独拆它的 lark-cli 配置流程。",
        "",
        "置顶评论：",
        "你们团队的飞书资料，最头疼的是 Wiki 归档、妙记整理，还是表格同步？",
    ]),
    "source_asset_manifest": manifest,
    "scenes": [
        {
            "visual_title": "真实 Skill 来源",
            "image_paths": [str((shots / "01-scope.png").resolve())],
            "image_labels": ["SOURCE"],
            "content_features": ["source", "skill", "scope"],
            "motion_direction": "zoom_in",
            "motion_amount": 0.06,
            "bottom_title": "飞书资料散在各处",
            "bottom_lines": [
                "文档、Wiki、表格和妙记经常分散在不同入口。",
                "手动复制最容易漏段、漏引用、漏会议转写。",
                "这个 Skill 的目标是先把来源忠实落到本地。",
                "交给知识库前，先拿到干净 Markdown。"
            ],
            "footer": "feishu-doc-scraper / source-grounded"
        },
        {
            "visual_title": "优先走 lark-cli",
            "image_paths": [str((shots / "02-api-path.png").resolve())],
            "image_labels": ["API"],
            "content_features": ["command", "code", "api"],
            "motion_direction": "local_zoom",
            "motion_focus": "left",
            "motion_amount": 0.08,
            "bottom_title": "优先走 API 抽取",
            "bottom_lines": [
                "正文通过 lark-cli 拉取，再用 jq 或 pandoc 写盘。",
                "关键点是程序抽取，不让模型重写原文。",
                "Wiki 节点会先解析成真正的文档 token。",
                "适合重视原文一致性的团队资料归档。"
            ],
            "footer": "API first / no model rewrite"
        },
        {
            "visual_title": "合集继续追引用",
            "image_paths": [str((shots / "03-recursion.png").resolve())],
            "image_labels": ["BFS"],
            "content_features": ["workflow", "reference", "recursion"],
            "motion_direction": "zoom_in",
            "motion_amount": 0.08,
            "bottom_title": "合集会继续追引用",
            "bottom_lines": [
                "合集页里的 mention-doc、sheet 和图片会先被枚举。",
                "脚本按引用图继续跑，直到没有新的叶子节点。",
                "这比只截当前页面稳，少很多沉默遗漏。",
                "抽取记录也能说明每份内容来自哪里。"
            ],
            "footer": "collection / reference graph"
        },
        {
            "visual_title": "权限边界清楚",
            "image_paths": [str((shots / "04-permission-boundary.png").resolve())],
            "image_labels": ["BOUNDARY"],
            "content_features": ["permission", "boundary"],
            "motion_direction": "zoom_in",
            "motion_amount": 0.06,
            "bottom_title": "权限不够就明说",
            "bottom_lines": [
                "遇到 131006 权限拒绝，它会当成真实边界。",
                "不靠匿名访问硬磨，也不假装能绕过去。",
                "正确做法是让权限持有人导出 docx。",
                "能抽的抽干净，抽不到的把缺口列清楚。"
            ],
            "footer": "permission-aware extraction"
        },
        {
            "visual_title": "交付前有验收",
            "image_paths": [str((shots / "05-acceptance.png").resolve())],
            "image_labels": ["CHECK"],
            "content_features": ["checklist", "acceptance"],
            "motion_direction": "zoom_in",
            "motion_amount": 0.08,
            "bottom_title": "适合沉淀团队知识库",
            "bottom_lines": [
                "最终要查残留标签、乱码和权限缺口。",
                "妙记转写保留平台原生结果，别重新 ASR。",
                "导出的 Markdown 再交给 Obsidian 或知识库。",
                "飞书资料多的团队，可以把它当归档入口。"
            ],
            "footer": "Markdown handoff / explicit gaps"
        }
    ]
}

profile_path = root / "inputs/repo_showcase_profile.json"
profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(profile_path)
PY
```

Expected: command exits `0` and prints `output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json`.

- [ ] **Step 2: Verify visible copy policy before rendering**

```bash
python3 - <<'PY'
import json
from pathlib import Path
profile = json.loads(Path("output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json").read_text(encoding="utf-8"))
forbidden = ["商用可用", "MIT", "链接", "网址", "扫码", "二维码", "URL", "不是", "而是"]
visible = [profile["top_title"], profile["top_subtitle"]]
for scene in profile["scenes"]:
    visible.extend([scene.get("visual_title", ""), scene.get("bottom_title", ""), scene.get("footer", "")])
    visible.extend(scene.get("bottom_lines", []))
text = "\n".join(visible)
hits = [term for term in forbidden if term in text]
assert not hits, hits
assert len(profile["scenes"]) == 5
assert profile["target_duration"] == 10
print("profile copy ok")
PY
```

Expected: `profile copy ok`.

## Task 3: Render Video With Repo Showcase Capsule

**Files:**
- Create: `output/feishu_doc_scraper_repo_showcase/render/release/video.mp4`
- Create: `output/feishu_doc_scraper_repo_showcase/render/release/copy.txt`
- Create: `output/feishu_doc_scraper_repo_showcase/render/qa/visible_copy_lint.json`
- Create: `output/feishu_doc_scraper_repo_showcase/render/qa/run_notes.json`
- Create: `output/feishu_doc_scraper_repo_showcase/render/artifact_manifest.json`

**Interfaces:**
- Consumes: profile JSON from Task 2.
- Produces: raw final video and renderer QA artifacts consumed by Task 4.

- [ ] **Step 1: Run renderer**

```bash
CAPSULE_CINEMA_ROOT=/Users/june2/code/github/capsule-cinema \
python3 /Users/june2/.codex/video-production/capsule_assets/repo_showcase/script/render_repo_showcase_video.py \
  --topic "feishu-doc-scraper" \
  --params /Users/june2/code/github/capsule-cinema/output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json \
  --output-dir /Users/june2/code/github/capsule-cinema/output/feishu_doc_scraper_repo_showcase/render
```

Expected: command exits `0`; `output/feishu_doc_scraper_repo_showcase/render/release/video.mp4` exists.

- [ ] **Step 2: Verify renderer outputs**

```bash
test -s output/feishu_doc_scraper_repo_showcase/render/release/video.mp4
test -s output/feishu_doc_scraper_repo_showcase/render/release/copy.txt
test -s output/feishu_doc_scraper_repo_showcase/render/artifact_manifest.json
test -s output/feishu_doc_scraper_repo_showcase/render/qa/run_notes.json
test -s output/feishu_doc_scraper_repo_showcase/render/qa/visible_copy_lint.json
```

Expected: all commands exit `0`.

## Task 4: QA And Release Package

**Files:**
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/public/video.mp4`
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/public/copy.txt`
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/qa/local_video_qa.json`
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/qa/source_asset_manifest.json`
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/technical/ffprobe.json`
- Create: `output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/README.md`
- Create: `output/feishu_doc_scraper_repo_showcase/CURRENT_RELEASE.md`

**Interfaces:**
- Consumes: raw video, copy, source manifest, and renderer QA artifacts from Task 3.
- Produces: release package paths used in final user response.

- [ ] **Step 1: Create release folders and copy public artifacts**

```bash
RELEASE=output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29
mkdir -p "$RELEASE/public" "$RELEASE/qa" "$RELEASE/technical" "$RELEASE/internal"
cp output/feishu_doc_scraper_repo_showcase/render/release/video.mp4 "$RELEASE/public/video.mp4"
cp output/feishu_doc_scraper_repo_showcase/render/release/copy.txt "$RELEASE/public/copy.txt"
cp output/feishu_doc_scraper_repo_showcase/inputs/source_asset_manifest.json "$RELEASE/qa/source_asset_manifest.json"
cp output/feishu_doc_scraper_repo_showcase/render/qa/visible_copy_lint.json "$RELEASE/qa/visible_copy_lint.json"
cp output/feishu_doc_scraper_repo_showcase/render/qa/run_notes.json "$RELEASE/technical/run_notes.json"
cp output/feishu_doc_scraper_repo_showcase/inputs/repo_showcase_profile.json "$RELEASE/internal/repo_showcase_profile.json"
```

Expected: command exits `0`.

- [ ] **Step 2: Run local video QA**

```bash
python3 scripts/local_video_qa.py \
  --run-dir /Users/june2/code/github/capsule-cinema/output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29 \
  --aspect-ratio "3:4" \
  --expect-audio \
  --output /Users/june2/code/github/capsule-cinema/output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/qa/local_video_qa.json
```

Expected: command exits `0` or writes a JSON report with actionable findings. If it cannot find the video because it expects `final/` or `release/`, run the direct `ffprobe` checks in Step 3 and keep the QA failure as a technical note.

- [ ] **Step 3: Write ffprobe technical metadata**

```bash
ffprobe -v error \
  -show_entries format=duration:stream=codec_type,width,height \
  -of json \
  output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/public/video.mp4 \
  > output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/technical/ffprobe.json
```

Expected: JSON contains one video stream with width `1080`, height `1440`, and at least one audio stream.

- [ ] **Step 4: Create release README and current-release pointer**

```bash
cat > output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29/README.md <<'MD'
# Feishu Doc Scraper Repo Showcase

Final public files:

- `public/video.mp4`
- `public/copy.txt`

QA files:

- `qa/local_video_qa.json`
- `qa/visible_copy_lint.json`
- `qa/source_asset_manifest.json`

Technical files:

- `technical/ffprobe.json`
- `technical/run_notes.json`

This release uses the `repo_showcase` capsule in 3:4 silent-card mode with packaged BGM.
MD

cat > output/feishu_doc_scraper_repo_showcase/CURRENT_RELEASE.md <<'MD'
# Current Release

Current approved candidate: `release/feishu-doc-scraper-2026-06-29`

Use `release/feishu-doc-scraper-2026-06-29/public/video.mp4` for review or publishing.
MD
```

Expected: both Markdown files exist.

- [ ] **Step 5: Final policy checks**

```bash
python3 - <<'PY'
import json
from pathlib import Path
release = Path("output/feishu_doc_scraper_repo_showcase/release/feishu-doc-scraper-2026-06-29")
copy = (release / "public/copy.txt").read_text(encoding="utf-8")
visible = (Path("output/feishu_doc_scraper_repo_showcase/render/qa/visible_text_for_lint.txt").read_text(encoding="utf-8"))
forbidden = ["商用可用", "MIT", "链接", "网址", "扫码", "二维码", "URL"]
hits = [term for term in forbidden if term in copy or term in visible]
assert not hits, hits
manifest = json.loads((release / "qa/source_asset_manifest.json").read_text(encoding="utf-8"))
assert len(manifest) == 5
assert all(item["reconstructed_card"] is False for item in manifest)
ffprobe = json.loads((release / "technical/ffprobe.json").read_text(encoding="utf-8"))
streams = ffprobe["streams"]
video = [s for s in streams if s.get("codec_type") == "video"][0]
audio = [s for s in streams if s.get("codec_type") == "audio"]
assert video["width"] == 1080 and video["height"] == 1440, video
assert audio, streams
print("final policy checks ok")
PY
```

Expected: `final policy checks ok`.

## Self-Review

- Spec coverage: Tasks cover source screenshots, profile copy, 3:4 silent renderer route, BGM-only render, release package, source manifest, visible lint, ffprobe, and local QA.
- Placeholder scan: Passed; all tasks include concrete commands, expected outputs, and exact paths.
- Type consistency: Task 1 produces PNG paths and manifest entries; Task 2 consumes those exact paths; Task 3 consumes `repo_showcase_profile.json`; Task 4 consumes renderer output and produces the final release package.
