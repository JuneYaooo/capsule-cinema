# Veo 3.1 Juling First/Last Frame Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `veo3.1` as a full-flow Juling video engine with first/last-frame generation.

**Architecture:** Add a separate `Veo31VideoGeneratorTool` that shares the existing Juling `/v1/videos` async pattern without changing the legacy `Veo3VideoGeneratorTool`. Register the new engine across runtime config, universal wrappers, OpenClaw metadata, docs, and README.

**Tech Stack:** Python 3.12, CrewAI `BaseTool`, Pydantic, `requests`, Node test runner, `unittest`.

## Global Constraints

- New engine name: `veo3.1`.
- Default model: `veo3.1_fast`, overridable with `JULING_VEO31_MODEL`.
- Provider/env: Juling via `JULING_BASE_URL` and `JULING_API_KEY`.
- First/last-frame payload: `model`, `prompt`, `type: 2`, `aspect_ratio`, `images`.
- Do not change or repoint `Veo3VideoGeneratorTool`.
- README user example must be short and must not include secret values.
- Do not hard-code API keys, bearer tokens, signed URLs, cookies, or private endpoints.

---

## File Structure

- Create `lib/custom_tools/video_generation/veo31_video_generator_tool.py`: schema, Juling client, image URL/data URI conversion, task polling, content download.
- Modify `lib/custom_tools/video_generation/video_generation_tool.py`: engine support, alias routing, `first_last_frame` route.
- Modify `lib/custom_tools/video_generation/__init__.py` and `lib/custom_tools/__init__.py`: exports.
- Modify `lib/config/tool_registry.yaml`, `lib/config/video_engines.yaml`, `lib/src/video_generation_config.py`, `scripts/capsule_runtime.py`: engine registration and aliases.
- Modify `skill.md`, `index.js`, `lib/config/env_registry.json`: OpenClaw metadata and env allowlist.
- Modify `references/*.md` and `README.md`: policy/API/usage docs and short user example.
- Modify tests: `tests/skill.test.js` plus Python unit tests for normalization, universal routing, and payload construction.

---

### Task 1: Failing Registration And Runtime Tests

**Files:**
- Modify: `tests/skill.test.js`
- Create: `tests/python/test_veo31_video_generator.py`
- Modify: `tests/python/test_storyboard_contract.py` only if an existing test helper is needed

**Interfaces:**
- Consumes: existing `normalize_video_engine_name(engine: str) -> str`
- Produces: failing expectations for `Veo31VideoGeneratorTool`, `veo3.1`, and first/last-frame payload construction

- [ ] **Step 1: Add JS registration expectations**

In `tests/skill.test.js`, extend `testVideoEngineSupportAlignment()`:

```js
const expected = ['seedance-fast', 'seedance', 'jimeng35pro', 'veo3', 'veo3.1'];
```

Add assertions near existing tool registry checks:

```js
const registryNames = loadToolRegistryNames();
assert.ok(registryNames.has('Veo31VideoGeneratorTool'), 'tool_registry.yaml 应注册 Veo31VideoGeneratorTool');
```

- [ ] **Step 2: Add Python tests for aliases, payload, and universal routing**

Create `tests/python/test_veo31_video_generator.py`:

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from custom_tools.video_generation.video_generation_tool import UniversalVideoGenerationTool
from src.video_generation_config import normalize_video_engine_name


class Veo31VideoGeneratorTests(unittest.TestCase):
    def test_normalizes_veo31_aliases(self):
        self.assertEqual(normalize_video_engine_name("veo31"), "veo3.1")
        self.assertEqual(normalize_video_engine_name("veo3_1"), "veo3.1")
        self.assertEqual(normalize_video_engine_name("veo3.1_fast"), "veo3.1")

    def test_client_builds_first_last_frame_payload(self):
        from custom_tools.video_generation.veo31_video_generator_tool import Veo31VideoClient

        with patch.dict(os.environ, {
            "JULING_BASE_URL": "https://example.test",
            "JULING_API_KEY": "secret",
            "JULING_VEO31_MODEL": "veo3.1_fast",
        }):
            client = Veo31VideoClient(output_dir="output/test_veo31")
            payload = client.build_payload(
                prompt="flowers grow",
                generation_type="first_last_frame",
                aspect_ratio="9:16",
                images=["https://example.test/start.jpg", "https://example.test/end.jpg"],
            )

        self.assertEqual(payload["model"], "veo3.1_fast")
        self.assertEqual(payload["prompt"], "flowers grow")
        self.assertEqual(payload["type"], 2)
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(payload["images"], ["https://example.test/start.jpg", "https://example.test/end.jpg"])

    def test_universal_tool_routes_first_last_frame(self):
        with patch("custom_tools.video_generation.video_generation_tool.Veo31VideoGeneratorTool") as tool_class:
            tool = Mock()
            tool._run.return_value = {"status": "success", "output_path": "output/test.mp4"}
            tool_class.return_value = tool

            result = UniversalVideoGenerationTool()._run(
                prompt="flowers grow",
                output_dir="output/test_veo31",
                generation_type="first_last_frame",
                engine="veo3.1",
                start_image_path="start.png",
                end_image_path="end.png",
                aspect_ratio="9:16",
            )

        self.assertEqual(result["output_path"], "output/test.mp4")
        tool._run.assert_called_once()
        self.assertEqual(tool._run.call_args.kwargs["generation_type"], "first_last_frame")
        self.assertEqual(tool._run.call_args.kwargs["start_image_path"], "start.png")
        self.assertEqual(tool._run.call_args.kwargs["end_image_path"], "end.png")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests and confirm RED**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_veo31_video_generator
node tests/skill.test.js
```

Expected:

- Python fails because `veo31_video_generator_tool.py` does not exist or aliases are unsupported.
- JS fails because `veo3.1` and `Veo31VideoGeneratorTool` are not registered.

- [ ] **Step 4: Commit failing tests**

```bash
git add tests/skill.test.js tests/python/test_veo31_video_generator.py
git commit -m "test: cover veo31 juling registration"
```

---

### Task 2: Implement The Veo 3.1 Tool

**Files:**
- Create: `lib/custom_tools/video_generation/veo31_video_generator_tool.py`
- Modify: `lib/custom_tools/video_generation/__init__.py`
- Modify: `lib/custom_tools/__init__.py`

**Interfaces:**
- Produces: `Veo31VideoClient.build_payload(...) -> dict`
- Produces: `Veo31VideoGeneratorTool._run(...) -> dict`
- Consumes: `JULING_BASE_URL`, `JULING_API_KEY`, optional `JULING_VEO31_MODEL`

- [ ] **Step 1: Implement schema, client, and tool**

Create `lib/custom_tools/video_generation/veo31_video_generator_tool.py` with:

```python
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import requests
from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.logger import get_logger

load_dotenv()
logger = get_logger("veo31_video_generator")


class Veo31VideoGeneratorSchema(BaseModel):
    prompt: str = Field(..., description="视频生成提示词")
    generation_type: str = Field("image_to_video", description="text_to_video | image_to_video | first_last_frame")
    output_dir: str = Field("output/manual_tool/work/videos/veo31", description="保存目录")
    output_path: Optional[str] = Field(None, description="完整输出路径，优先于 output_dir")
    image_path: Optional[str] = Field(None, description="单图图生视频输入")
    start_image_path: Optional[str] = Field(None, description="首帧图片路径或 URL")
    end_image_path: Optional[str] = Field(None, description="尾帧图片路径或 URL")
    images: Optional[List[str]] = Field(None, description="首尾帧图片 URL/path 列表")
    aspect_ratio: str = Field("9:16", description="9:16 / 16:9 / 1:1")
    model: Optional[str] = Field(None, description="默认 JULING_VEO31_MODEL 或 veo3.1_fast")


class Veo31VideoClient:
    POLL_INTERVAL = 8
    POLL_TIMEOUT = 1200

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, output_dir: str = "output/manual_tool/work/videos/veo31"):
        self.api_key = api_key or os.getenv("JULING_API_KEY")
        self.base_url = (base_url or os.getenv("JULING_BASE_URL") or "").rstrip("/")
        self.model = os.getenv("JULING_VEO31_MODEL", "veo3.1_fast")
        if not self.api_key:
            raise ValueError("Missing required env var: JULING_API_KEY")
        if not self.base_url:
            raise ValueError("Missing required env var: JULING_BASE_URL")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def image_to_url(self, image: str) -> str:
        if image.startswith("http://") or image.startswith("https://") or image.startswith("data:image/"):
            return image
        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {path}")
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/jpeg")
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('utf-8')}"

    def normalize_images(
        self,
        generation_type: str,
        image_path: Optional[str],
        start_image_path: Optional[str],
        end_image_path: Optional[str],
        images: Optional[List[str]],
    ) -> List[str]:
        if generation_type == "first_last_frame":
            selected = images or [start_image_path, end_image_path]
            selected = [item for item in selected if item]
            if len(selected) != 2:
                raise ValueError("first_last_frame requires exactly two images via images or start_image_path/end_image_path")
            return [self.image_to_url(item) for item in selected]
        if generation_type == "image_to_video":
            if not image_path:
                raise ValueError("image_to_video requires image_path")
            return [self.image_to_url(image_path)]
        return []

    def build_payload(
        self,
        prompt: str,
        generation_type: str,
        aspect_ratio: str,
        images: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }
        if generation_type == "first_last_frame":
            if not images or len(images) != 2:
                raise ValueError("first_last_frame requires exactly two images")
            payload["type"] = 2
            payload["images"] = images
        elif generation_type == "image_to_video":
            if not images or len(images) != 1:
                raise ValueError("image_to_video requires exactly one image")
            payload["type"] = 1
            payload["images"] = images
        elif generation_type == "text_to_video":
            payload["type"] = 0
        else:
            raise ValueError(f"Unsupported generation_type: {generation_type}")
        return payload

    def create_task(self, payload: Dict[str, Any]) -> str:
        resp = requests.post(f"{self.base_url}/v1/videos", json=payload, headers=self.headers, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id") or data.get("task_id") or data.get("video_id")
        if not task_id:
            raise ValueError(f"未获取到任务ID，响应字段: {list(data.keys())}")
        return str(task_id)

    def query_task(self, task_id: str) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/v1/videos/{task_id}", headers=self.headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def poll_until_done(self, task_id: str) -> Dict[str, Any]:
        started = time.time()
        while time.time() - started < self.POLL_TIMEOUT:
            data = self.query_task(task_id)
            status = str(data.get("status", "")).lower()
            if status in {"success", "completed", "done"}:
                return data
            if status in {"failed", "error"}:
                raise RuntimeError(data.get("error") or data.get("message") or "视频任务失败")
            time.sleep(self.POLL_INTERVAL)
        raise TimeoutError(f"任务超时（已等待 {self.POLL_TIMEOUT}s）")

    def resolve_output_path(self, output_path: Optional[str], prefix: str) -> Path:
        if output_path:
            path = Path(output_path)
        else:
            path = self.output_dir / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def download_result(self, task_id: str, result: Dict[str, Any], output_path: Path) -> str:
        video_url = result.get("video_url") or result.get("url") or result.get("output_url")
        url = video_url or f"{self.base_url}/v1/videos/{task_id}/content"
        resp = requests.get(url, headers=self.headers if not video_url else None, stream=True, timeout=300)
        resp.raise_for_status()
        with output_path.open("wb") as handle:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
        return str(output_path)

    def generate(
        self,
        prompt: str,
        generation_type: str,
        aspect_ratio: str,
        output_path: Optional[str],
        image_path: Optional[str],
        start_image_path: Optional[str],
        end_image_path: Optional[str],
        images: Optional[List[str]],
        model: Optional[str],
    ) -> str:
        normalized_images = self.normalize_images(generation_type, image_path, start_image_path, end_image_path, images)
        payload = self.build_payload(prompt, generation_type, aspect_ratio, normalized_images, model=model)
        task_id = self.create_task(payload)
        result = self.poll_until_done(task_id)
        target = self.resolve_output_path(output_path, generation_type)
        return self.download_result(task_id, result, target)


class Veo31VideoGeneratorTool(BaseTool):
    name: str = "Veo3.1视频生成工具"
    description: str = "使用 Juling veo3.1_fast 生成视频，支持文生视频、单图图生视频和首尾帧视频。"
    args_schema: Type[BaseModel] = Veo31VideoGeneratorSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "image_to_video",
        output_dir: str = "output/manual_tool/work/videos/veo31",
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[List[str]] = None,
        aspect_ratio: str = "9:16",
        model: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        try:
            client = Veo31VideoClient(output_dir=output_dir)
            final_path = client.generate(
                prompt=prompt,
                generation_type=generation_type,
                aspect_ratio=aspect_ratio,
                output_path=output_path,
                image_path=image_path,
                start_image_path=start_image_path,
                end_image_path=end_image_path,
                images=images,
                model=model,
            )
            return {
                "status": "success",
                "engine": "veo3.1",
                "generation_type": generation_type,
                "output_path": final_path,
            }
        except Exception as exc:
            logger.error(f"Veo3.1 视频生成失败: {exc}")
            return {"status": "failed", "engine": "veo3.1", "error": str(exc)}
```

- [ ] **Step 2: Export the tool**

In `lib/custom_tools/video_generation/__init__.py` add:

```python
from .veo31_video_generator_tool import Veo31VideoGeneratorTool
```

and add `'Veo31VideoGeneratorTool'` to `__all__`.

In `lib/custom_tools/__init__.py` add:

```python
"Veo31VideoGeneratorTool": "custom_tools.video_generation",
```

- [ ] **Step 3: Run Python test and confirm partial GREEN**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_veo31_video_generator
```

Expected: payload construction passes; universal routing may still fail until Task 3.

- [ ] **Step 4: Commit**

```bash
git add lib/custom_tools/video_generation/veo31_video_generator_tool.py lib/custom_tools/video_generation/__init__.py lib/custom_tools/__init__.py
git commit -m "feat: add veo31 juling video tool"
```

---

### Task 3: Register `veo3.1` In Runtime Flow

**Files:**
- Modify: `lib/custom_tools/video_generation/video_generation_tool.py`
- Modify: `lib/src/video_generation_config.py`
- Modify: `lib/config/tool_registry.yaml`
- Modify: `lib/config/video_engines.yaml`
- Modify: `scripts/capsule_runtime.py`
- Modify: `scripts/run_video.py`
- Modify: `scripts/run_scene.py`
- Modify: `scripts/run_language_check.py`
- Modify: `lib/video_workflows/general_video/tasks.py`

**Interfaces:**
- Consumes: `Veo31VideoGeneratorTool._run(...)`
- Produces: `engine="veo3.1"` support in direct, universal, full-video, and feedback routes

- [ ] **Step 1: Add engine aliases and support lists**

In `lib/src/video_generation_config.py`, add `veo3.1` to:

```python
SUPPORTED_VIDEO_ENGINES: List[str] = field(
    default_factory=lambda: ["seedance-fast", "seedance", "jimeng35pro", "veo3", "veo3.1"]
)
VIDEO_ENGINE_FALLBACK_ORDER: List[str] = field(
    default_factory=lambda: ["seedance-fast", "jimeng35pro", "veo3.1", "veo3"]
)
```

Add aliases:

```python
"veo31": "veo3.1",
"veo3-1": "veo3.1",
"veo3.1-fast": "veo3.1",
"veo3.1_fast": "veo3.1",
```

- [ ] **Step 2: Route universal video generation**

In `lib/custom_tools/video_generation/video_generation_tool.py`:

```python
from .veo31_video_generator_tool import Veo31VideoGeneratorTool
SUPPORTED_VIDEO_ENGINES = {"seedance-fast", "seedance", "jimeng35pro", "veo3", "veo3.1"}
CHINESE_PROMPT_ENGINES = {"seedance-fast", "seedance", "jimeng35pro", "veo3", "veo3.1"}
```

Update `_tool_for_engine`:

```python
if engine == "veo3.1":
    return Veo31VideoGeneratorTool()
```

Update schemas to mention `first_last_frame` and add optional fields:

```python
start_image_path: Optional[str] = Field(None, description="Start frame path/URL for first_last_frame")
end_image_path: Optional[str] = Field(None, description="End frame path/URL for first_last_frame")
images: Optional[List[str]] = Field(None, description="Image list for first_last_frame")
```

Update `UniversalVideoGenerationTool._run(...)` to accept those params and route:

```python
if generation_type == "first_last_frame":
    result = _tool_for_engine(engine)._run(
        prompt=prompt,
        generation_type="first_last_frame",
        output_dir=output_dir,
        start_image_path=start_image_path,
        end_image_path=end_image_path,
        images=images,
        aspect_ratio=aspect_ratio,
        **kwargs,
    )
    video_path = _video_path_from_result(result)
    return {"engine": engine, "generation_type": "first_last_frame", "result": result, "output_path": video_path} if video_path else {"error": str(result), "engine": engine}
```

- [ ] **Step 3: Register config metadata**

Add to `lib/config/tool_registry.yaml`:

```yaml
  Veo31VideoGeneratorTool:
    module: custom_tools.video_generation.veo31_video_generator_tool
    category: video_generation
    provider: juling
    limits:
      duration_options: [8]
      aspect_ratios: ["16:9", "9:16", "1:1"]
    strengths: [high_quality, cinematic, first_last_frame]
```

Add to `lib/config/video_engines.yaml`:

```yaml
  veo3.1:
    name: Veo 3.1 Fast
    provider: juling
    capabilities:
      duration_options: [8]
      default_duration: 8
      aspect_ratios: ["16:9", "9:16", "1:1"]
    features:
      text_to_video: true
      image_to_video: true
      transition_frames: true
    best_for: [高画质, 电影感, 首尾帧转场]
    strengths: [首尾帧控制, 画质好, Juling统一接口]
    weaknesses: [较慢, 需要首尾帧质量稳定]
    cost_tier: high
```

Update `selection_rules.supported` and `compatibility.pure_image_to_video`.

- [ ] **Step 4: Update scripts and planning prompt text**

In `scripts/capsule_runtime.py` add:

```python
"Veo31VideoGeneratorTool": "veo3.1",
```

Update help text in `scripts/run_video.py` and `scripts/run_scene.py` to include `veo3.1`.

Keep `scripts/run_language_check.py` generation retry support limited to the
existing speech-oriented engines. Do not add `veo3.1` retry execution there;
only update comments/help text if needed so the script does not imply it can
regenerate Veo 3.1 speech-language failures.

In `lib/video_workflows/general_video/tasks.py`, update engine selection text to include:

```text
- `veo3.1`：Juling Veo 3.1 Fast，支持首尾帧，适合高画质转场
```

and allow `"video_engine": "seedance-fast / seedance / jimeng35pro / veo3 / veo3.1"`.

- [ ] **Step 5: Run tests and confirm GREEN for runtime**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_veo31_video_generator
node tests/skill.test.js
```

Expected: new Python tests pass; JS alignment test passes.

- [ ] **Step 6: Commit**

```bash
git add lib/custom_tools/video_generation/video_generation_tool.py lib/src/video_generation_config.py lib/config/tool_registry.yaml lib/config/video_engines.yaml scripts/capsule_runtime.py scripts/run_video.py scripts/run_scene.py scripts/run_language_check.py lib/video_workflows/general_video/tasks.py
git commit -m "feat: register veo31 video engine"
```

---

### Task 4: Metadata, Docs, README Example, And Verification

**Files:**
- Modify: `skill.md`
- Modify: `index.js`
- Modify: `lib/config/env_registry.json`
- Modify: `references/channel-policy.md`
- Modify: `references/tools-api.md`
- Modify: `references/engines-and-voices.md`
- Modify: `references/video-recipes.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: registered `Veo31VideoGeneratorTool`
- Produces: public usage docs and OpenClaw env pass-through support

- [ ] **Step 1: Update env metadata and skill docs**

Add `JULING_VEO31_MODEL` to `skill.md` permissions env and common env table.

Add `JULING_VEO31_MODEL` to `index.js` `ALLOWED_ENV_KEYS`.

Add to `lib/config/env_registry.json`:

```json
{
  "key": "JULING_VEO31_MODEL",
  "category": "image_video",
  "openclaw": true,
  "secret": false,
  "description": "Optional Juling Veo 3.1 model override; default is veo3.1_fast."
}
```

- [ ] **Step 2: Update policy and API docs**

In `references/channel-policy.md`, add `Veo31VideoGeneratorTool` under approved video tools with:

```markdown
### `Veo31VideoGeneratorTool` - Juling Veo 3.1 Fast

- Channel: Juling
- Env: `JULING_API_KEY`, `JULING_BASE_URL`, optional `JULING_VEO31_MODEL`
- Modes: `text_to_video`, `image_to_video`, `first_last_frame`
- Strengths: high-quality transitions controlled by start and end frames
- Gotcha: for `first_last_frame`, provide two stable frames with matching subject, framing, and aspect ratio.
```

In `references/tools-api.md`, add a short direct call example:

```bash
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool Veo31VideoGeneratorTool \
  --params '{"prompt":"花瓶里的端午花草从空瓶逐渐生长并开花，古风画卷质感，镜头稳定推进","generation_type":"first_last_frame","start_image_path":"'"$RUN_ROOT"'/work/images/vase_start.png","end_image_path":"'"$RUN_ROOT"'/work/images/vase_end.png","output_dir":"'"$RUN_ROOT"'/work/videos","output_path":"'"$RUN_ROOT"'/work/videos/vase_veo31.mp4","aspect_ratio":"9:16"}'
```

Update `references/engines-and-voices.md` and `references/video-recipes.md` with one-line entries for `veo3.1`.

- [ ] **Step 3: Add short README example**

In `README.md`, add a concise section:

```markdown
### Veo 3.1 首尾帧视频

```bash
RUN_ROOT="$PWD/output/manual_veo31_vase"
mkdir -p "$RUN_ROOT"/work/{images,videos}

PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool GptImage2Tool \
  --params '{"prompt":"古风画卷质感，一只空花瓶置于宣纸背景前，静物构图，留白雅致，无文字","output_path":"'"$RUN_ROOT"'/work/images/vase_start.png","aspect_ratio":"9:16"}'

PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool GptImage2Tool \
  --params '{"prompt":"同一只古风空花瓶中插满端午花草，艾草、菖蒲和淡雅花朵自然舒展，古风画卷质感，无文字","output_path":"'"$RUN_ROOT"'/work/images/vase_end.png","aspect_ratio":"9:16"}'

PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool Veo31VideoGeneratorTool \
  --params '{"prompt":"花瓶里的端午花草从空瓶逐渐生长并开花，古风画卷质感，镜头稳定推进","generation_type":"first_last_frame","start_image_path":"'"$RUN_ROOT"'/work/images/vase_start.png","end_image_path":"'"$RUN_ROOT"'/work/images/vase_end.png","output_dir":"'"$RUN_ROOT"'/work/videos","output_path":"'"$RUN_ROOT"'/work/videos/vase_veo31.mp4","aspect_ratio":"9:16"}'
```
```

- [ ] **Step 4: Run verification**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_veo31_video_generator
node tests/skill.test.js
python3.12 -m py_compile lib/custom_tools/video_generation/veo31_video_generator_tool.py lib/custom_tools/video_generation/video_generation_tool.py lib/src/video_generation_config.py
npm test
```

Expected: all pass. If `npm test` is blocked by unrelated existing tests or missing dependencies, capture the exact blocker.

- [ ] **Step 5: Commit**

```bash
git add skill.md index.js lib/config/env_registry.json references/channel-policy.md references/tools-api.md references/engines-and-voices.md references/video-recipes.md README.md
git commit -m "docs: add veo31 usage example"
```

---

## Final Review

- [ ] `git status --short` contains only expected changes or is clean.
- [ ] No secret values are present in code, docs, logs, or examples.
- [ ] The existing `Veo3VideoGeneratorTool` file is unchanged except unrelated imports if necessary.
- [ ] `Veo31VideoGeneratorTool` is registered in `tool_registry.yaml`.
- [ ] `video_engine=veo3.1` is accepted by runtime config and universal wrappers.
- [ ] README contains the short vase example.
