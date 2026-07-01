# Runtime Behavior Logic Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix delivery-promise inference, video fallback completion, and full-video progress monitoring without broad workspace or capsule refactors.

**Architecture:** Keep public OpenClaw inputs and outputs stable. Add small, focused helpers at existing runtime boundaries: `run_video.py` owns CLI-level delivery intent, `VideoGenerator` owns scene-level fallback completion, and `index.js` owns stdout event parsing and progress monitor lifecycle.

**Tech Stack:** Node.js ES modules, Python 3.12, `unittest`, existing Python runtime modules under `lib/`, existing OpenClaw adapter in `index.js`.

## Global Constraints

- Do not modify capsule package content in `capsules/`.
- Do not unify all workspace creation helpers in this slice.
- Do not introduce a full `RuntimePlan` abstraction in this slice.
- Keep `build_delivery_promise(... needs_audio=...)` compatible.
- Existing `npm test` must continue to pass.
- Add focused regression tests for behavior changed in this slice.

---

## File Structure

- Modify `scripts/run_video.py`: add narration-intent helper, pass it into `build_delivery_promise`, emit workspace progress event through callback.
- Modify `lib/video_workflows/general_video/flow.py`: accept and forward optional `progress_callback`.
- Modify `lib/video_workflows/general_video/crew.py`: accept optional `progress_callback`, call it after workspace setup.
- Modify `lib/src/runtime/general_video_crew/video_generator.py`: change engine fallback from batch-threshold stop to missing-scene completion.
- Modify `index.js`: parse stdout JSONL progress events, start workspace monitor when `workspace_created` appears, preserve final JSON parsing.
- Add `tests/python/test_run_video_delivery_intent.py`: regression tests for narration intent helper.
- Add `tests/python/test_video_generator_fallback_completion.py`: regression tests for scene-completion fallback.
- Extend `tests/skill.test.js`: tests for progress event parsing or exported helper behavior.

---

### Task 1: Delivery Promise Narration Intent

**Files:**
- Modify: `scripts/run_video.py`
- Create: `tests/python/test_run_video_delivery_intent.py`

**Interfaces:**
- Produces: `infer_narration_intent(user_requirements: str, capsule: dict | None = None) -> bool`
- Consumes: existing `build_delivery_promise(... needs_audio=...)`

- [ ] **Step 1: Write failing tests**

Create `tests/python/test_run_video_delivery_intent.py`:

```python
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_video.py"


def load_run_video():
    spec = importlib.util.spec_from_file_location("run_video_for_delivery_intent", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryIntentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_video = load_run_video()

    def test_plain_subtitled_video_does_not_imply_tts_explainer(self):
        self.assertFalse(
            self.run_video.infer_narration_intent(
                "做一个 30 秒竖屏短视频，主题是一只橘猫做饭",
                capsule=None,
            )
        )

    def test_explicit_voiceover_text_implies_tts_explainer(self):
        self.assertTrue(
            self.run_video.infer_narration_intent(
                "做一个 30 秒讲解视频，需要旁白配音",
                capsule=None,
            )
        )

    def test_capsule_has_narration_implies_tts_explainer(self):
        capsule = {"config": {"has_narration": True}}

        self.assertTrue(
            self.run_video.infer_narration_intent(
                "做一期胶囊视频",
                capsule=capsule,
            )
        )

    def test_capsule_unified_tts_contract_implies_tts_explainer(self):
        capsule = {"config": {"output_contract": {"voice": "unified_tts"}}}

        self.assertTrue(
            self.run_video.infer_narration_intent(
                "做一期胶囊视频",
                capsule=capsule,
            )
        )

    def test_no_narration_capsule_overrides_generic_text(self):
        capsule = {"config": {"has_narration": False, "output_contract": {"voice": "none"}}}

        self.assertFalse(
            self.run_video.infer_narration_intent(
                "做一个带字幕的视频",
                capsule=capsule,
            )
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_run_video_delivery_intent -v
```

Expected: fails because `infer_narration_intent` does not exist.

- [ ] **Step 3: Implement minimal helper**

In `scripts/run_video.py`, add near `str2bool`:

```python
NARRATION_INTENT_MARKERS = (
    "旁白",
    "讲解",
    "配音",
    "口播",
    "voiceover",
    "narration",
    "narrator",
)


def infer_narration_intent(user_requirements: str, capsule: dict | None = None) -> bool:
    capsule = capsule or {}
    config = capsule.get("config") if isinstance(capsule.get("config"), dict) else {}
    output_contract = config.get("output_contract") if isinstance(config.get("output_contract"), dict) else {}

    if config.get("has_narration") is False or output_contract.get("voice") == "none":
        return False
    if config.get("has_narration") is True or output_contract.get("voice") == "unified_tts":
        return True

    text = str(user_requirements or "").lower()
    return any(marker in text for marker in NARRATION_INTENT_MARKERS)
```

Then change the `build_delivery_promise` call:

```python
needs_audio=infer_narration_intent(user_requirements, capsule),
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_run_video_delivery_intent -v
PYTHONPATH=lib python3.12 -m unittest tests.python.test_production_contract -v
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_video.py tests/python/test_run_video_delivery_intent.py
git commit -m "fix: infer narration intent for delivery promise"
```

---

### Task 2: Video Fallback Completes Missing Scenes

**Files:**
- Modify: `lib/src/runtime/general_video_crew/video_generator.py`
- Create: `tests/python/test_video_generator_fallback_completion.py`

**Interfaces:**
- Produces internal helper behavior in `VideoGenerator.generate_videos(...)`: outputs preserve successful scene indices and retry only missing scene indices.
- Consumes existing `_fallback_engines`, `_generate_video_batch`, `_analyze_and_regenerate_videos`, `_fallback_to_image_videos`.

- [ ] **Step 1: Write failing partial-engine test**

Create `tests/python/test_video_generator_fallback_completion.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from src.runtime.general_video_crew.video_generator import VideoGenerator  # noqa: E402


def make_storyboard(count=3):
    return [
        {"index": idx + 1, "video_prompt": f"scene {idx + 1}"}
        for idx in range(count)
    ]


def make_image_result(tmpdir, count=3):
    outputs = {}
    for idx in range(count):
        path = Path(tmpdir) / f"scene_{idx + 1}.png"
        path.write_bytes(b"fake image")
        outputs[idx] = str(path)
    return {"outputs": outputs}


class VideoFallbackCompletionTest(unittest.TestCase):
    def test_fallback_engine_fills_only_missing_scenes(self):
        calls = []
        generator = VideoGenerator()

        def fake_fallback_engines(_engine, required_flags=None):
            return ["engine_a", "engine_b"]

        def fake_generate(scene_list, image_outputs, output_dir, engine, aspect_ratio, execution_directive=None):
            original_indices = [original for original, _scene in scene_list]
            calls.append((engine, original_indices))
            if engine == "engine_a":
                return {0: str(Path(output_dir) / "scene_1.mp4")}
            return {idx: str(Path(output_dir) / f"scene_{idx + 1}.mp4") for idx in original_indices}

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(generator, "_fallback_engines", fake_fallback_engines), \
             patch.object(generator, "_generate_video_batch", fake_generate), \
             patch.object(generator, "_analyze_and_regenerate_videos", side_effect=lambda video_outputs, **_kwargs: video_outputs):
            result = generator.generate_videos(
                storyboard=make_storyboard(3),
                image_result=make_image_result(tmpdir, 3),
                output_dir=tmpdir,
                engine="engine_a",
                enable_quality_check=True,
            )

        self.assertEqual(calls, [("engine_a", [0, 1, 2]), ("engine_b", [1, 2])])
        self.assertEqual(result["summary"]["generated"], 3)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(set(result["outputs"]), {0, 1, 2})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_video_generator_fallback_completion -v
```

Expected: fails because current implementation stops after 70% success or reruns the full batch instead of only missing scenes.

- [ ] **Step 3: Implement missing-scene completion**

In `VideoGenerator.generate_videos`, replace the fallback loop with this structure:

```python
all_outputs = {}
last_error = None

for current_engine in fallback_engines:
    missing_indices = [
        index
        for index in range(len(storyboard))
        if not self._is_valid_output(all_outputs.get(index))
    ]
    if not missing_indices:
        break
    logger.info(f"🎬 使用视频生成引擎: {current_engine}，补齐 {len(missing_indices)} 个场景")
    try:
        scene_list = [(index, storyboard[index]) for index in missing_indices]
        partial_outputs = self._generate_video_batch(
            scene_list=scene_list,
            image_outputs=image_outputs,
            output_dir=output_dir,
            engine=current_engine,
            aspect_ratio=aspect_ratio,
            execution_directive=execution_directive,
        )
        if enable_quality_check and partial_outputs:
            partial_outputs = self._analyze_and_regenerate_videos(
                video_outputs=partial_outputs,
                scene_list=scene_list,
                image_outputs=image_outputs,
                output_dir=output_dir,
                engine=current_engine,
                max_regeneration_attempts=max_regeneration_attempts,
                execution_directive=execution_directive,
            )
        for index, path in partial_outputs.items():
            if self._is_valid_output(path):
                all_outputs[index] = path
    except Exception as exc:
        last_error = str(exc)
        logger.error(f"❌ 视频引擎 {current_engine} 失败: {last_error}")
```

Add helper:

```python
@staticmethod
def _is_valid_output(value: object) -> bool:
    return bool(value and isinstance(value, str) and not value.startswith("错误"))
```

Update `_build_video_result` to use `_is_valid_output`.

- [ ] **Step 4: Add and pass static fallback missing-only test**

Append to `VideoFallbackCompletionTest`:

```python
    def test_static_fallback_only_fills_missing_scenes(self):
        calls = []
        generator = VideoGenerator()

        def fake_fallback_engines(_engine, required_flags=None):
            return ["engine_a"]

        def fake_generate(scene_list, image_outputs, output_dir, engine, aspect_ratio, execution_directive=None):
            return {0: str(Path(output_dir) / "scene_1.mp4")}

        def fake_fallback(storyboard, image_outputs, output_dir, animation_type="auto"):
            calls.append([scene.get("index") for scene in storyboard])
            return {
                idx: str(Path(output_dir) / f"fallback_{idx + 1}.mp4")
                for idx in range(len(storyboard))
            }

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(generator, "_fallback_engines", fake_fallback_engines), \
             patch.object(generator, "_generate_video_batch", fake_generate), \
             patch.object(generator, "_fallback_to_image_videos", fake_fallback):
            result = generator.generate_videos(
                storyboard=make_storyboard(3),
                image_result=make_image_result(tmpdir, 3),
                output_dir=tmpdir,
                engine="engine_a",
                enable_quality_check=False,
                allow_static_fallback=True,
            )

        self.assertEqual(calls, [[2, 3]])
        self.assertEqual(result["summary"]["generated"], 3)
        self.assertEqual(result["summary"]["failed"], 0)
```

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest tests.python.test_video_generator_fallback_completion -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add lib/src/runtime/general_video_crew/video_generator.py tests/python/test_video_generator_fallback_completion.py
git commit -m "fix: complete missing scene videos with fallback engines"
```

---

### Task 3: Full-Video Workspace Progress Event

**Files:**
- Modify: `scripts/run_video.py`
- Modify: `lib/video_workflows/general_video/flow.py`
- Modify: `lib/video_workflows/general_video/crew.py`
- Modify: `index.js`
- Modify: `tests/skill.test.js`

**Interfaces:**
- Produces Python callback chain: `progress_callback(event: str, **payload) -> None`
- Produces JS helper: `extractProgressEvents(text: string) -> Array<object>`
- Produces JS helper: `extractWorkspaceFromProgress(text: string) -> string | null`

- [ ] **Step 1: Add JS parsing tests**

In `tests/skill.test.js`, add near other helper tests:

```javascript
async function testProgressEventParsing() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  assert.ok(typeof mod.extractProgressEvents === 'function', 'index.js 应导出 extractProgressEvents');
  assert.ok(typeof mod.extractWorkspaceFromProgress === 'function', 'index.js 应导出 extractWorkspaceFromProgress');

  const text = [
    'log line',
    '{"event":"workspace_created","workspace_dir":"/tmp/capsule/output/general_video_1"}',
    '{"success":true,"workspace_dir":"/tmp/final"}',
  ].join('\n');

  const events = mod.extractProgressEvents(text);
  assert.strictEqual(events.length, 1, '只应提取 event JSON，不应把最终结果当 progress event');
  assert.strictEqual(events[0].event, 'workspace_created');
  assert.strictEqual(
    mod.extractWorkspaceFromProgress(text),
    '/tmp/capsule/output/general_video_1'
  );

  console.log('  ✅ progress event 解析验证通过');
}
```

Add `await testProgressEventParsing();` in the async test runner section near other async tests.

- [ ] **Step 2: Run JS test and verify failure**

Run:

```bash
node tests/skill.test.js
```

Expected: fails because `extractProgressEvents` is not exported.

- [ ] **Step 3: Implement JS progress event helpers**

In `index.js`, add after `parseOutput`:

```javascript
function extractProgressEvents(text) {
  const events = [];
  for (const rawLine of String(text || '').split('\n')) {
    const line = rawLine.trim();
    if (!line.startsWith('{')) continue;
    try {
      const data = JSON.parse(line);
      if (data && typeof data === 'object' && data.event) {
        events.push(data);
      }
    } catch {
      // Ignore non-JSON log fragments.
    }
  }
  return events;
}

function extractWorkspaceFromProgress(text) {
  for (const event of extractProgressEvents(text)) {
    if (event.event === 'workspace_created' && event.workspace_dir) {
      return String(event.workspace_dir);
    }
  }
  return null;
}
```

Export both helpers at the bottom of `index.js`.

- [ ] **Step 4: Start monitor from stdout event**

In `index.js`, change `runPythonScript` to accept an optional stdout hook:

```javascript
function runPythonScript(scriptName, args, context, options = {}) {
  const scriptPath = join(SCRIPTS_DIR, scriptName);
  const { env: safeEnv, pythonBin } = buildSafeEnv(context);

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonBin, [scriptPath, ...args], {
      cwd: SKILL_DIR,
      env: safeEnv,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      if (typeof options.onStdoutText === 'function') {
        options.onStdoutText(text);
      }
      if (context.sendProgressUpdate) {
        context.sendProgressUpdate(text.trim());
      }
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(
          `脚本执行失败（exit code ${code}）:\n${stderr || stdout}`
        ));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`无法启动 Python 进程: ${err.message}`));
    });
  });
}
```

In `execute`, replace the fixed monitor with a mutable monitor:

```javascript
let monitoredWorkspace = inputs.workspace_dir || workspace?.workspace_dir || null;
let activeMonitor = startWorkspaceMonitor(monitoredWorkspace, context);
let stdout = '';
try {
  ({ stdout } = await runPythonScript(route.script, args, context, {
    onStdoutText(text) {
      const eventWorkspace = extractWorkspaceFromProgress(text);
      if (eventWorkspace && !monitoredWorkspace) {
        monitoredWorkspace = eventWorkspace;
        activeMonitor.stop();
        activeMonitor = startWorkspaceMonitor(monitoredWorkspace, context);
      }
    },
  }));
} finally {
  activeMonitor.stop();
}
```

Keep final artifact collection using:

```javascript
const knownWorkspace = result.workspace_dir || monitoredWorkspace || workspace?.workspace_dir || null;
const artifacts = collectWorkspaceArtifacts(knownWorkspace);
```

- [ ] **Step 5: Add Python callback chain**

In `scripts/run_video.py`, add:

```python
def emit_progress_event(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)
```

Pass callback:

```python
result = run_general_video_flow(
    user_requirements=user_requirements,
    target_duration=target_duration,
    progress_callback=emit_progress_event,
    **kwargs,
)
```

In `flow.py`, include the callback in the existing `self.state` dictionary:

```python
crew_result = self.crew.kickoff(self.state)
```

Add this key to the existing state literal in `AgnoGeneralVideoFlow.run`:

```python
'progress_callback': kwargs.get('progress_callback'),
```

In `crew.py`, after `self.setup_workspace(video_name)`:

```python
progress_callback = state.get("progress_callback")
if callable(progress_callback):
    progress_callback("workspace_created", workspace_dir=str(self.workspace_dir))
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
node tests/skill.test.js
npm test
```

Expected: both pass.

Commit:

```bash
git add index.js scripts/run_video.py lib/video_workflows/general_video/flow.py lib/video_workflows/general_video/crew.py tests/skill.test.js
git commit -m "fix: expose full video workspace progress"
```

---

### Task 4: Final Verification

**Files:**
- Verify all changed files.

**Interfaces:**
- Consumes all prior tasks.
- Produces verified working tree changes for runtime behavior optimization.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
PYTHONPATH=lib python3.12 -m unittest \
  tests.python.test_run_video_delivery_intent \
  tests.python.test_video_generator_fallback_completion \
  tests.python.test_production_contract \
  -v
```

Expected: all tests pass.

- [ ] **Step 2: Run Node adapter tests**

Run:

```bash
node tests/skill.test.js
```

Expected: all tests pass.

- [ ] **Step 3: Run package test**

Run:

```bash
npm test
```

Expected: `py_compile` exits 0.

- [ ] **Step 4: Inspect diff scope**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: no `capsules/` files modified by this slice; changes are limited to runtime files and tests.

- [ ] **Step 5: Final commit if needed**

If prior task commits were not created, commit the completed runtime optimization:

```bash
git add index.js scripts/run_video.py lib/video_workflows/general_video/flow.py lib/video_workflows/general_video/crew.py lib/src/runtime/general_video_crew/video_generator.py tests/skill.test.js tests/python/test_run_video_delivery_intent.py tests/python/test_video_generator_fallback_completion.py
git commit -m "fix: optimize runtime behavior logic"
```
