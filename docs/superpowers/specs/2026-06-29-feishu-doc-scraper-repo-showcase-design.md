# Feishu Doc Scraper Repo Showcase Video Design

Date: 2026-06-29

## Goal

Create a short `repo_showcase` capsule video for `feishu-doc-scraper`, aimed at Chinese office-productivity users who use Feishu/Lark for team documents, Wiki pages, spreadsheets, and meeting transcripts.

The video should make one clear promise: Feishu content can be extracted faithfully into local Markdown without hand-copying, while respecting permission boundaries and extraction fidelity.

## Route

- Capsule: `repo_showcase`
- Format: 3:4, 1080x1440
- Duration: about 10 seconds
- Scenes: 5
- Audio: packaged BGM only
- Voiceover: none
- Subtitles: none
- Public CTA inside video: none

This follows the current `repo_showcase` contract: silent structured cards, real source visuals in the middle panel, and dense bottom copy for value translation.

## Target Audience

Primary users:

- Domestic knowledge workers using Feishu for daily documents, Wiki pages, and project archives.
- Operators, assistants, researchers, PMs, and developers who need to move Feishu content into Markdown, local notes, or knowledge-base workflows.
- Teams that care about faithful extraction more than AI rewriting.

Non-target users:

- Viewers looking for a permission bypass tool.
- Viewers expecting Google Workspace automation.
- Viewers expecting a full tutorial inside one 10-second video.

## Public Angle

Recommended title:

> 飞书文档，别再手动复制了

The framing should avoid generic "AI tool" language. It should say what this skill is and why it matters:

- Feishu/Lark source to faithful local Markdown.
- Works with docs, Wiki, sheets, and Minutes.
- Uses `lark-cli` API as the primary path.
- Recurses through referenced docs in collections.
- Treats permission-denied cases as hard boundaries rather than guessing or bypassing.

## Scene Plan

1. Pain
   - Middle visual: real `SKILL.md` opening or scope section.
   - Bottom title: `飞书资料散在各处`
   - Bottom lines explain that docs, Wiki, sheets, and Minutes are easy to lose when copied by hand.

2. Primary Path
   - Middle visual: real Path A / `lark-cli` command section.
   - Bottom title: `优先走 API 抽取`
   - Bottom lines explain that the document body is fetched programmatically and written to disk, not rewritten by the model.

3. Collection Recursion
   - Middle visual: decision tree or reference-extraction command.
   - Bottom title: `合集会继续追引用`
   - Bottom lines explain that hub pages and referenced docs are followed until leaf nodes, reducing silent omissions.

4. Permission Boundary
   - Middle visual: permission-denied / Path B section.
   - Bottom title: `权限不够就明说`
   - Bottom lines explain that 131006 permission denial is treated as a real Feishu-side boundary, not something to brute-force.

5. Office Workflow Value
   - Middle visual: acceptance contract or hard rules section.
   - Bottom title: `适合沉淀团队知识库`
   - Bottom lines explain use cases: archive Feishu docs, preserve meeting transcripts, feed PKM or knowledge-base ingestion, and keep gaps explicit.

## Source Material

Use real local source material from:

- `/Users/june2/code/github/skills_meterial/office-productivity-skills/skills/office-documents/daymade_claude-code-skills__feishu-doc-scraper/SKILL.md`
- Direct references under that skill directory only if needed for richer source screenshots.

No generated concept art, stock images, AI summary cards, browser chrome, URLs, QR codes, or visible links should appear in public video frames. Screenshots must show source content regions only.

## Copy Rules

Visible copy must:

- Use Chinese office-productivity language.
- Explain concrete input, mechanism, output, and boundary.
- Keep claims grounded in the skill file.
- Avoid "商用可用", "MIT", URLs, links, QR-code language, and internal production terms.
- Avoid "X 不是 Y，而是 Z" style formulaic copy.
- Avoid promising permission bypass or guaranteed complete extraction when the source is inaccessible.

Publishing copy should be separate from the video and can invite a concrete comment, such as asking viewers whether they want the next video to show the exact `lark-cli` setup flow.

## Deliverables

The production run should create a release-style package with:

- Final 3:4 video.
- Copywriting file.
- Source-asset manifest listing every real visual source.
- Visible text lint report.
- Local video QA report.
- Capsule run notes.

## QA Gates

Before delivery:

- Verify final video exists and has audio.
- Verify aspect ratio is 3:4.
- Inspect key frames for readable top title, middle source visual, and bottom card text.
- Run visible-copy lint.
- Confirm no visible URLs, domains, QR codes, or "链接/网址/扫码" language.
- Confirm all middle visuals are actual source screenshots or other approved real source assets.
- Confirm no voiceover or subtitle artifacts were introduced.

## Open Decisions

None. The user approved the domestic office-productivity angle, 3:4 silent `repo_showcase` route, and approximately 10-second BGM-only format.
