# Video To Capsule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `video-to-capsule` workflow that analyzes a local video with a registry-selected analyzer, writes analysis/draft artifacts, and optionally creates a valid active capsule package.

**Architecture:** Add the workflow as a separate OpenClaw route and Python CLI so existing generation routes do not change. Put normalization and package-writing logic in `lib/src/video_to_capsule.py` for network-free unit tests. Use existing capsule package scaffolding and validation to create active packages.

**Tech Stack:** Node.js ES modules for `index.js` adapter tests, Python 3.12 scripts and helpers, PyYAML, existing capsule package create/validate scripts, existing `Gemini3VideoAnalyzerTool`.

## Global Constraints

- The workflow is two-step by default: generate analysis and a draft first, write a package only when explicitly requested.
- Video analysis models are selected through the existing tool registry and capability layer, not hard-coded into the workflow.
- The analysis keeps both levels of output: scene/beat-level evidence plus capsule-level reusable rules.
- The source video is not packaged by default. If `include_source_video=true`, it is copied into the capsule as a `reference_only` asset.
- The active capsule package must not store `video_breakdown.json` or `analyzer_raw_response.json`.
- Default `video_analysis_tool` is `Gemini3VideoAnalyzerTool`.
- Use TDD: write each failing test, run it, implement the smallest code, rerun it.

---

## File Structure

- Modify `lib/config/capabilities.yaml`: add `video_analysis` modality vocabulary.
- Modify `lib/config/tool_capabilities.yaml`: register `Gemini3VideoAnalyzerTool` as `video_analysis`.
- Modify `lib/config/tool_registry.yaml`: keep callable mapping and set analyzer category to `video_analysis`.
- Modify `lib/config/env_registry.json`: expose `GEMINI3_MODEL_NAME` to OpenClaw because model selection is user configuration for the Gemini analyzer.
- Modify `skill.md`: add capability, inputs, outputs, and env key for the workflow.
- Modify `index.js`: add route, args, parsing, output fields, and allowed env key.
- Modify `package.json`: include the new CLI script in `npm test` py_compile list.
- Create `lib/src/video_to_capsule.py`: pure helpers for parsing analyzer output, building artifacts, and writing package surfaces.
- Create `scripts/analyze_video_to_capsule.py`: CLI orchestration entry point.
- Create `tests/python/test_video_to_capsule.py`: unit tests for helper and CLI behavior.
- Modify `tests/skill.test.js`: adapter and metadata tests for workflow surface.

---

### Task 1: Registry, Capability, And OpenClaw Surface

**Files:**
- Modify: `lib/config/capabilities.yaml`
- Modify: `lib/config/tool_capabilities.yaml`
- Modify: `lib/config/tool_registry.yaml`
- Modify: `lib/config/env_registry.json`
- Modify: `skill.md`
- Modify: `index.js`
- Modify: `tests/skill.test.js`

**Interfaces:**
- Consumes: existing YAML registry files and `assertSkillDeclaresIo(name, section)` in `tests/skill.test.js`.
- Produces: `workflow=video-to-capsule`, inputs `source_video_path`, `video_analysis_tool`, `write_capsule`, `include_source_video`, and outputs `video_analysis_path`, `capsule_draft_path`, `capsule_dir`, `analysis_tool_used`, `warnings`.

- [ ] **Step 1: Write failing Node metadata and adapter tests**

Add these tests in `tests/skill.test.js` before the test list:

```js
function testVideoToCapsuleOpenClawSurface() {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const indexContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const capabilities = readFileSync(join(SKILL_DIR, 'lib', 'config', 'capabilities.yaml'), 'utf-8');
  const toolCapabilities = readFileSync(join(SKILL_DIR, 'lib', 'config', 'tool_capabilities.yaml'), 'utf-8');
  const toolRegistry = readFileSync(join(SKILL_DIR, 'lib', 'config', 'tool_registry.yaml'), 'utf-8');
  const envRegistry = JSON.parse(readFileSync(join(SKILL_DIR, 'lib', 'config', 'env_registry.json'), 'utf-8'));

  assert.ok(skillContent.includes('id: analyze-video-to-capsule'), 'skill.md 应声明视频解析成胶囊能力');
  for (const inputName of [
    'source_video_path',
    'video_analysis_tool',
    'capsule_name',
    'write_capsule',
    'include_source_video',
  ]) {
    assertSkillDeclaresIo(inputName, 'inputs');
  }
  for (const outputName of [
    'video_analysis_path',
    'capsule_draft_path',
    'capsule_dir',
    'analysis_tool_used',
    'warnings',
  ]) {
    assertSkillDeclaresIo(outputName, 'outputs');
  }
  assert.ok(indexContent.includes("'video-to-capsule'"), 'index.js 应声明 video-to-capsule route');
  assert.ok(indexContent.includes('analyze_video_to_capsule.py'), 'index.js 应路由到 analyze_video_to_capsule.py');
  assert.ok(capabilities.includes('video_analysis:'), 'capabilities.yaml 应声明 video_analysis modality');
  assert.ok(toolCapabilities.includes('Gemini3VideoAnalyzerTool:'), 'tool_capabilities.yaml 应登记 Gemini3VideoAnalyzerTool');
  assert.ok(toolCapabilities.includes('modality: video_analysis'), 'Gemini3VideoAnalyzerTool modality 应为 video_analysis');
  assert.ok(toolRegistry.includes('category: video_analysis'), 'tool_registry.yaml 应将 analyzer 分类为 video_analysis');
  assert.ok(envRegistry.env.some(item => item.key === 'GEMINI3_MODEL_NAME' && item.openclaw === true), 'GEMINI3_MODEL_NAME 应允许用户配置');

  console.log('  ✅ 视频解析成胶囊 OpenClaw surface 验证通过');
}
```

Add it to the `tests` list:

```js
['视频解析成胶囊 surface', testVideoToCapsuleOpenClawSurface],
```

- [ ] **Step 2: Run Node test to verify it fails**

Run:

```bash
node tests/skill.test.js
```

Expected: FAIL with an assertion that `skill.md 应声明视频解析成胶囊能力` or `index.js 应声明 video-to-capsule route`.

- [ ] **Step 3: Add registry and skill metadata**

Patch the files as follows:

```yaml
# lib/config/capabilities.yaml under modalities:
  video_analysis:
    flags:
      source_video_analysis: 本地源视频多模态解析
      scene_breakdown: 逐镜头/逐时间段拆解
      capsule_recipe_inference: 从视频分析提炼胶囊配方规则
    tags:
      - gemini
      - multimodal
      - recipe_inference
```

```yaml
# lib/config/tool_capabilities.yaml under tools:
  Gemini3VideoAnalyzerTool:
    module: custom_tools.quality_check.gemini3_video_analyzer
    modality: video_analysis
    provides:
      flags: {source_video_analysis: true, scene_breakdown: true, capsule_recipe_inference: true}
    tags: [gemini, multimodal, recipe_inference]
    requires_env: [GEMINI3_API_KEY, GEMINI3_BASE_URL]
    cost_tier: medium
    capability_source: manual
```

Change `lib/config/tool_registry.yaml`:

```yaml
  Gemini3VideoAnalyzerTool:
    module: custom_tools.quality_check.gemini3_video_analyzer
    category: video_analysis
    provider: gemini
```

Change the `GEMINI3_MODEL_NAME` entry in `lib/config/env_registry.json`:

```json
{
  "key": "GEMINI3_MODEL_NAME",
  "category": "llm",
  "openclaw": true,
  "secret": false,
  "description": "Gemini 3 video analysis model name."
}
```

Add `GEMINI3_MODEL_NAME` to `skill.md.permissions.env` and `ALLOWED_ENV_KEYS` in `index.js`.

Add a capability to `skill.md`:

```yaml
  - id: analyze-video-to-capsule
    description: "使用用户配置的视频解析工具分析本地视频，生成胶囊草稿，并可显式写入 active 胶囊包"
```

Add inputs to `skill.md`:

```yaml
  - name: source_video_path
    type: string
    required: false
    description: "video-to-capsule 工作流的本地源视频路径"
  - name: video_analysis_tool
    type: string
    required: false
    default: "Gemini3VideoAnalyzerTool"
    description: "视频解析工具名，来自 tool_registry.yaml，例如 Gemini3VideoAnalyzerTool"
  - name: capsule_name
    type: string
    required: false
    description: "写入胶囊时使用的安全短名；write_capsule=true 时必填"
  - name: capsule_display_name
    type: string
    required: false
    description: "可选胶囊展示名；不传时从 capsule_name 生成"
  - name: capsule_summary
    type: string
    required: false
    description: "可选胶囊摘要；不传时使用解析结果摘要"
  - name: write_capsule
    type: boolean
    required: false
    default: false
    description: "是否把草稿写成 capsules/<name>.capsule/ active 胶囊包"
  - name: include_source_video
    type: boolean
    required: false
    default: false
    description: "写胶囊时是否把源视频作为 reference_only 资产打包"
  - name: overwrite_capsule
    type: boolean
    required: false
    default: false
    description: "目标胶囊已存在时是否允许覆盖"
  - name: analysis_prompt
    type: string
    required: false
    description: "追加给视频解析模型的自定义分析要求"
  - name: target_platform
    type: string
    required: false
    description: "可选发布平台提示，用于解析和胶囊草稿提炼"
```

Add outputs to `skill.md`:

```yaml
  - name: video_analysis_path
    type: string
    description: "analysis/video_breakdown.json 路径"
  - name: capsule_draft_path
    type: string
    description: "analysis/capsule_draft.json 路径"
  - name: capsule_dir
    type: string
    description: "write_capsule=true 时创建的 active 胶囊目录"
  - name: analysis_tool_used
    type: string
    description: "实际使用的视频解析工具"
  - name: warnings
    type: object
    description: "解析或写胶囊过程中的非阻断警告"
```

- [ ] **Step 4: Add minimal adapter route constants**

In `index.js`, add:

```js
  'video-to-capsule': { script: 'analyze_video_to_capsule.py', workflow: 'E', supports_output_dir: false },
```

In `SCRIPT_PARAM_MAP`, add:

```js
  'analyze_video_to_capsule.py': {
    source_video_path: '--source-video-path',
    video_analysis_tool: '--video-analysis-tool',
    capsule_name: '--capsule-name',
    capsule_display_name: '--capsule-display-name',
    capsule_summary: '--capsule-summary',
    analysis_prompt: '--analysis-prompt',
    target_platform: '--target-platform',
    write_capsule: { flag: '--write-capsule', type: 'boolean' },
    include_source_video: { flag: '--include-source-video', type: 'boolean' },
    overwrite_capsule: { flag: '--overwrite-capsule', type: 'boolean' },
  },
```

In `execute()`, add validation:

```js
  if (workflow === 'video-to-capsule' && !inputs.source_video_path) {
    throw new Error('视频解析成胶囊工作流需要指定 source_video_path。');
  }
```

- [ ] **Step 5: Run Node test to verify it passes**

Run:

```bash
node tests/skill.test.js
```

Expected: PASS for `视频解析成胶囊 surface`.

- [ ] **Step 6: Commit task 1**

Run:

```bash
git add lib/config/capabilities.yaml lib/config/tool_capabilities.yaml lib/config/tool_registry.yaml lib/config/env_registry.json skill.md index.js tests/skill.test.js
git commit -m "feat: expose video to capsule workflow surface"
```

---

### Task 2: Pure Video-To-Capsule Contracts

**Files:**
- Create: `lib/src/video_to_capsule.py`
- Create: `tests/python/test_video_to_capsule.py`

**Interfaces:**
- Consumes: analyzer result dictionaries returned by `Gemini3VideoAnalyzerTool._run`.
- Produces:
  - `build_analysis_prompt(analysis_prompt: str = "", target_platform: str = "") -> str`
  - `normalize_video_analysis(raw_result: dict, source_video_path: str, analysis_tool: str, capsule_name: str = "", capsule_display_name: str = "", capsule_summary: str = "", target_platform: str = "") -> tuple[dict, dict]`
  - `write_json(path: Path, payload: dict) -> Path`
  - `write_artifact_manifest(workspace_dir: Path, artifacts: list[dict]) -> Path`
  - `materialize_capsule_from_draft(draft: dict, source_video_path: str, output_root: Path, include_source_video: bool = False, overwrite: bool = False) -> Path`

- [ ] **Step 1: Write failing normalizer tests**

Create `tests/python/test_video_to_capsule.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SCRIPTS = ROOT / "scripts"
for path in (LIB, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class VideoToCapsuleContractTest(unittest.TestCase):
    def test_normalize_complete_analysis_builds_breakdown_and_draft(self):
        from src.video_to_capsule import normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "sample.mp4"
            video_path.write_bytes(b"fake video")
            raw = {
                "success": True,
                "summary": "A punchy product demo with fast captions.",
                "source_profile": {
                    "likely_format": "product_showcase",
                    "aspect_ratio": "9:16",
                    "target_platform": "douyin",
                    "primary_audience": "young shoppers",
                },
                "segments": [
                    {
                        "start_time": "00:00.000",
                        "end_time": "00:03.000",
                        "beat": "Hook shows the product result first.",
                        "visuals": "Macro product close-up with clean background.",
                        "motion": "Fast push-in and hard cut.",
                        "copy": "Large benefit caption.",
                        "audio": "Energetic music hit.",
                        "reuse_lesson": "Open with final benefit before explaining features.",
                    }
                ],
                "capsule_recipe": {
                    "when_to_use": ["product demo", "benefit-led short video"],
                    "when_not_to_use": ["slow documentary"],
                    "structure_rules": ["Open with the strongest visible result."],
                    "copy_rules": ["Keep hook caption under 12 Chinese characters."],
                    "visual_rules": ["Use macro close-ups for tactile proof."],
                    "audio_rules": ["Sync first cut to a music hit."],
                    "motion_rules": ["Use fast push-in on the first beat."],
                    "quality_rules": ["Product must remain readable in every segment."],
                    "default_runtime": {"aspect_ratio": "9:16", "target_duration": 30},
                },
                "warnings": ["one subtitle is partially occluded"],
            }

            breakdown, draft = normalize_video_analysis(
                raw,
                source_video_path=str(video_path),
                analysis_tool="Gemini3VideoAnalyzerTool",
                capsule_name="product_demo_capsule",
                capsule_display_name="Product Demo Capsule",
                target_platform="douyin",
            )

        self.assertEqual("capsule_cinema.video_breakdown.v1", breakdown["schema_version"])
        self.assertEqual("Gemini3VideoAnalyzerTool", breakdown["analysis_tool"])
        self.assertEqual(1, len(breakdown["segments"]))
        self.assertEqual("capsule_cinema.capsule_draft.v1", draft["schema_version"])
        self.assertEqual("product_demo_capsule", draft["name"])
        self.assertEqual("Product Demo Capsule", draft["display_name"])
        self.assertEqual("product_showcase", draft["category"])
        self.assertIn("image_to_video", draft["capabilities"])
        self.assertEqual("Open with the strongest visible result.", draft["recipes"]["structure"][0])
        self.assertEqual("Product must remain readable in every segment.", draft["quality_rules"][0]["rule"])
        self.assertEqual("9:16", draft["runtime"]["defaults"]["aspect_ratio"])

    def test_normalize_blocks_failed_analysis(self):
        from src.video_to_capsule import VideoToCapsuleError, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "sample.mp4"
            video_path.write_bytes(b"fake video")
            with self.assertRaises(VideoToCapsuleError):
                normalize_video_analysis(
                    {"success": False, "error": "analysis unavailable"},
                    source_video_path=str(video_path),
                    analysis_tool="Gemini3VideoAnalyzerTool",
                    capsule_name="bad_capsule",
                )

    def test_materialize_capsule_does_not_copy_source_by_default(self):
        from src.video_to_capsule import materialize_capsule_from_draft, normalize_video_analysis
        from capsule_package_validate import validate_capsule_dir

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "sample.mp4"
            video_path.write_bytes(b"fake video")
            _, draft = normalize_video_analysis(
                {
                    "success": True,
                    "summary": "Demo summary",
                    "segments": [],
                    "capsule_recipe": {"structure_rules": ["Use a clear hook."]},
                },
                source_video_path=str(video_path),
                analysis_tool="FakeAnalyzerTool",
                capsule_name="demo_capsule",
            )

            cap_dir = materialize_capsule_from_draft(
                draft,
                source_video_path=str(video_path),
                output_root=tmp_path / "capsules",
            )

            report = validate_capsule_dir(cap_dir, warnings_ok=True)
            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))

        self.assertTrue(report["ok"])
        self.assertEqual([], assets["assets"])
        self.assertFalse((cap_dir / "assets" / "source_video.mp4").exists())

    def test_materialize_capsule_can_include_reference_only_source_video(self):
        from src.video_to_capsule import materialize_capsule_from_draft, normalize_video_analysis

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "sample.mp4"
            video_path.write_bytes(b"fake video")
            _, draft = normalize_video_analysis(
                {
                    "success": True,
                    "summary": "Demo summary",
                    "segments": [],
                    "capsule_recipe": {"visual_rules": ["Match the source lighting rhythm."]},
                },
                source_video_path=str(video_path),
                analysis_tool="FakeAnalyzerTool",
                capsule_name="demo_capsule",
            )

            cap_dir = materialize_capsule_from_draft(
                draft,
                source_video_path=str(video_path),
                output_root=tmp_path / "capsules",
                include_source_video=True,
            )
            assets = yaml.safe_load((cap_dir / "assets" / "index.yaml").read_text(encoding="utf-8"))

        self.assertTrue((cap_dir / "assets" / "source_video.mp4").is_file())
        self.assertEqual("reference_only", assets["assets"][0]["reuse"])
        self.assertEqual("source_video_reference", assets["assets"][0]["role"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_video_to_capsule -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.video_to_capsule'`.

- [ ] **Step 3: Implement helper module**

Create `lib/src/video_to_capsule.py` with functions named in this task. The implementation must:

```python
class VideoToCapsuleError(Exception):
    """Raised when source video analysis cannot produce a usable capsule draft."""
```

Use these constants:

```python
BREAKDOWN_SCHEMA = "capsule_cinema.video_breakdown.v1"
DRAFT_SCHEMA = "capsule_cinema.capsule_draft.v1"
SAFE_CAPSULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
RECIPE_DOMAINS = ("structure", "copy", "visual", "audio", "motion")
```

`normalize_video_analysis()` must:

```python
if not raw_result.get("success", True):
    raise VideoToCapsuleError(str(raw_result.get("error") or "video analysis failed"))
```

Build `breakdown` with keys:

```python
{
    "schema_version": BREAKDOWN_SCHEMA,
    "source_video": {"path": str(Path(source_video_path).expanduser()), "filename": Path(source_video_path).name},
    "analysis_tool": analysis_tool,
    "summary": summary,
    "source_profile": source_profile,
    "segments": normalized_segments,
    "warnings": warnings,
}
```

Build `draft` with keys:

```python
{
    "schema_version": DRAFT_SCHEMA,
    "name": safe_name,
    "display_name": display_name,
    "summary": summary,
    "category": category,
    "primary_workflow": "generic_ai_video",
    "capabilities": capabilities,
    "tags": tags,
    "when_to_use": when_to_use,
    "when_not_to_use": when_not_to_use,
    "input_schema": {"fields": {"topic": {"type": "string", "required": True, "description": "Primary topic for videos made with this inferred capsule."}}},
    "runtime": {"defaults": default_runtime, "output_contract": {"final_video": "required"}},
    "recipes": {"structure": structure_rules, "copy": copy_rules, "visual": visual_rules, "audio": audio_rules, "motion": motion_rules},
    "quality_rules": quality_rule_dicts,
    "lessons": lesson_dicts,
    "analysis": {"tool": analysis_tool, "source_summary": summary, "segment_count": len(normalized_segments)},
}
```

`materialize_capsule_from_draft()` must call `create_capsule_package()`, then rewrite recipe, runtime, input, quality, learning, and asset surfaces, and finally call `validate_capsule_dir(cap_dir, warnings_ok=True)`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_video_to_capsule -v
```

Expected: PASS all four tests.

- [ ] **Step 5: Commit task 2**

Run:

```bash
git add lib/src/video_to_capsule.py tests/python/test_video_to_capsule.py
git commit -m "feat: add video to capsule contracts"
```

---

### Task 3: CLI Workflow Script

**Files:**
- Create: `scripts/analyze_video_to_capsule.py`
- Modify: `package.json`
- Modify: `tests/python/test_video_to_capsule.py`

**Interfaces:**
- Consumes: `load_tool_registry()` shape from `scripts/run_tool.py` and helper functions from `src.video_to_capsule`.
- Produces CLI JSON output with `workspace_dir`, `video_analysis_path`, `capsule_draft_path`, `capsule_dir`, `analysis_tool_used`, `warnings`.

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/python/test_video_to_capsule.py`:

```python
class VideoToCapsuleCliTest(unittest.TestCase):
    def test_cli_draft_only_writes_analysis_artifacts_with_fake_tool(self):
        import analyze_video_to_capsule

        class FakeAnalyzerTool:
            def _run(self, **kwargs):
                return {
                    "success": True,
                    "summary": "Fast explainer",
                    "segments": [{"beat": "Hook first", "reuse_lesson": "Start with a direct problem."}],
                    "capsule_recipe": {"structure_rules": ["Start with a direct problem."]},
                    "warnings": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp4"
            source.write_bytes(b"fake video")
            result = analyze_video_to_capsule.run_video_to_capsule(
                source_video_path=str(source),
                video_analysis_tool="FakeAnalyzerTool",
                output_base_dir=tmp_path / "output",
                capsule_name="fast_explainer",
                tool_factory=lambda _name: FakeAnalyzerTool(),
            )

            analysis_path = Path(result["video_analysis_path"])
            draft_path = Path(result["capsule_draft_path"])

        self.assertTrue(analysis_path.is_file())
        self.assertTrue(draft_path.is_file())
        self.assertIsNone(result["capsule_dir"])
        self.assertEqual("FakeAnalyzerTool", result["analysis_tool_used"])

    def test_cli_write_capsule_creates_package_with_fake_tool(self):
        import analyze_video_to_capsule

        class FakeAnalyzerTool:
            def _run(self, **kwargs):
                return {
                    "success": True,
                    "summary": "Fast explainer",
                    "segments": [{"beat": "Hook first", "reuse_lesson": "Start with a direct problem."}],
                    "capsule_recipe": {"structure_rules": ["Start with a direct problem."]},
                    "warnings": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp4"
            source.write_bytes(b"fake video")
            result = analyze_video_to_capsule.run_video_to_capsule(
                source_video_path=str(source),
                video_analysis_tool="FakeAnalyzerTool",
                output_base_dir=tmp_path / "output",
                capsule_output_root=tmp_path / "capsules",
                capsule_name="fast_explainer",
                write_capsule=True,
                include_source_video=True,
                tool_factory=lambda _name: FakeAnalyzerTool(),
            )

            cap_dir = Path(result["capsule_dir"])

        self.assertTrue((cap_dir / "capsule.yaml").is_file())
        self.assertTrue((cap_dir / "assets" / "source_video.mp4").is_file())
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_video_to_capsule.VideoToCapsuleCliTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'analyze_video_to_capsule'`.

- [ ] **Step 3: Implement CLI script**

Create `scripts/analyze_video_to_capsule.py` with:

```python
def load_tool_registry() -> dict[str, str]:
    registry_path = _LIB_DIR / "config" / "tool_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    return {name: cfg["module"] for name, cfg in (data.get("tools") or {}).items() if isinstance(cfg, dict) and cfg.get("module")}
```

```python
def instantiate_tool(tool_name: str):
    registry = load_tool_registry()
    if tool_name not in registry:
        raise SystemExit(f"unknown video analysis tool: {tool_name}")
    module = importlib.import_module(registry[tool_name])
    tool_class = getattr(module, tool_name)
    tool = tool_class()
    if not hasattr(tool, "_run"):
        raise SystemExit(f"video analysis tool does not expose _run: {tool_name}")
    return tool
```

```python
def run_video_to_capsule(..., tool_factory=instantiate_tool) -> dict:
    source = Path(source_video_path).expanduser()
    if not source.is_file():
        raise SystemExit(f"source video not found: {source}")
    workspace = create_workspace_dir(output_base_dir)
    prompt = build_analysis_prompt(analysis_prompt, target_platform)
    tool = tool_factory(video_analysis_tool)
    raw = tool._run(video_path=str(source), prompt=prompt, analysis_focus="content")
    breakdown, draft = normalize_video_analysis(...)
    write analysis JSON files
    if write_capsule:
        cap_dir = materialize_capsule_from_draft(...)
    elif include_source_video:
        warnings.append("include_source_video ignored because write_capsule is false")
    write artifact_manifest.json
    return result
```

The CLI `main()` must parse flags exactly matching `index.js`:

```text
--source-video-path
--video-analysis-tool
--capsule-name
--capsule-display-name
--capsule-summary
--analysis-prompt
--target-platform
--write-capsule
--include-source-video
--overwrite-capsule
--output-base-dir
--capsule-output-root
```

Add `scripts/analyze_video_to_capsule.py` to the py_compile list in `package.json`.

- [ ] **Step 4: Run CLI tests to verify they pass**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_video_to_capsule.VideoToCapsuleCliTest -v
```

Expected: PASS both CLI tests.

- [ ] **Step 5: Commit task 3**

Run:

```bash
git add scripts/analyze_video_to_capsule.py package.json tests/python/test_video_to_capsule.py
git commit -m "feat: add video to capsule cli"
```

---

### Task 4: OpenClaw Adapter Execution Outputs

**Files:**
- Modify: `index.js`
- Modify: `tests/skill.test.js`

**Interfaces:**
- Consumes: JSON stdout from `scripts/analyze_video_to_capsule.py`.
- Produces: OpenClaw result fields `video_analysis_path`, `capsule_draft_path`, `capsule_dir`, `analysis_tool_used`, and `warnings`.

- [ ] **Step 1: Write failing parseOutput test**

Add this test in `tests/skill.test.js`:

```js
async function testParseVideoToCapsuleOutput() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  const parsed = mod.parseOutput(JSON.stringify({
    workspace_dir: '/tmp/run',
    video_analysis_path: '/tmp/run/analysis/video_breakdown.json',
    capsule_draft_path: '/tmp/run/analysis/capsule_draft.json',
    capsule_dir: '/tmp/capsules/demo.capsule',
    capsule_name: 'demo',
    analysis_tool_used: 'Gemini3VideoAnalyzerTool',
    warnings: ['source video not packaged']
  }));

  assert.strictEqual(parsed.video_analysis_path, '/tmp/run/analysis/video_breakdown.json');
  assert.strictEqual(parsed.capsule_draft_path, '/tmp/run/analysis/capsule_draft.json');
  assert.strictEqual(parsed.capsule_dir, '/tmp/capsules/demo.capsule');
  assert.strictEqual(parsed.analysis_tool_used, 'Gemini3VideoAnalyzerTool');
  assert.deepStrictEqual(parsed.warnings, ['source video not packaged']);

  console.log('  ✅ video-to-capsule parseOutput 验证通过');
}
```

Add to the `tests` list:

```js
['video-to-capsule output 解析', testParseVideoToCapsuleOutput],
```

- [ ] **Step 2: Run Node test to verify it fails**

Run:

```bash
node tests/skill.test.js
```

Expected: FAIL because `parsed.video_analysis_path` is `undefined`.

- [ ] **Step 3: Extend parseOutput and execute return**

In `parseOutput(stdout)`, add fields when JSON is parsed:

```js
video_analysis_path: data.video_analysis_path || null,
capsule_draft_path: data.capsule_draft_path || null,
capsule_dir: data.capsule_dir || null,
capsule_name: data.capsule_name || null,
analysis_tool_used: data.analysis_tool_used || null,
warnings: data.warnings || [],
```

In the final `return` object from `execute()`, add:

```js
video_analysis_path: result.video_analysis_path || null,
capsule_draft_path: result.capsule_draft_path || null,
capsule_dir: result.capsule_dir || null,
capsule_name: result.capsule_name || inputs.capsule_name || null,
analysis_tool_used: result.analysis_tool_used || inputs.video_analysis_tool || null,
warnings: result.warnings || [],
```

- [ ] **Step 4: Run Node test to verify it passes**

Run:

```bash
node tests/skill.test.js
```

Expected: PASS for `video-to-capsule output 解析`.

- [ ] **Step 5: Commit task 4**

Run:

```bash
git add index.js tests/skill.test.js
git commit -m "feat: return video to capsule artifacts"
```

---

### Task 5: Final Verification

**Files:**
- Verify all modified files from prior tasks.

**Interfaces:**
- Consumes: repository test commands.
- Produces: verified working feature.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
PYTHONPATH=lib:scripts python3.12 -m unittest tests.python.test_video_to_capsule -v
```

Expected: PASS all tests.

- [ ] **Step 2: Run Node skill tests**

Run:

```bash
node tests/skill.test.js
```

Expected: PASS all tests.

- [ ] **Step 3: Run package py_compile baseline**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 4: Review status**

Run:

```bash
git status --short
```

Expected: only unrelated pre-existing untracked files remain, or a clean status if all task files were committed.

- [ ] **Step 5: Final commit if any task file remains unstaged**

Run:

```bash
git add index.js package.json skill.md lib/config/capabilities.yaml lib/config/tool_capabilities.yaml lib/config/tool_registry.yaml lib/config/env_registry.json lib/src/video_to_capsule.py scripts/analyze_video_to_capsule.py tests/skill.test.js tests/python/test_video_to_capsule.py
git commit -m "feat: add video to capsule workflow"
```

Skip this commit if prior task commits already included every changed task file.

---

## Self-Review

- Spec coverage: tasks cover workflow route, tool registry selection, two-level artifacts, optional package writing, opt-in source video asset, OpenClaw inputs/outputs, and tests.
- Placeholder scan: no task uses incomplete placeholders; every code step names concrete functions, files, and commands.
- Type consistency: `video_analysis_path`, `capsule_draft_path`, `capsule_dir`, `capsule_name`, `analysis_tool_used`, and `warnings` are consistent across CLI, adapter, outputs, and tests.
