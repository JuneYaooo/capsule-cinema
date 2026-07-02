# Style Consistency Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a framework-level visual consistency contract so style and character drift are blocked by runtime QA instead of hidden inside prompt fallbacks.

**Architecture:** Implement a pure helper in `lib/src` for prompt compilation and prompt-index validation, then wire its report into deterministic score/release gates. `life_sim` consumes the shared contract through runtime YAML flags and dry-run validation instead of owning the architecture itself.

**Tech Stack:** Python 3.12, `unittest`, YAML runtime contracts, existing `scripts/score_video_quality.py`, `scripts/release_checkpoint.py`, and capsule package contracts.

## Global Constraints

- Do not call paid image/video APIs.
- Do not write API keys, cookies, signed URLs, or private endpoints to files, manifests, docs, command args, or logs.
- Do not create one-off scripts under `output/`.
- Keep the contract provider-agnostic and cross-capsule.
- Keep `life_sim` as a consumer of the shared contract, not the owner of the design.
- Use TDD: write a failing focused test before each production change.

---

### Task 1: Shared Visual Consistency Helper

**Files:**
- Create: `tests/python/test_visual_consistency_contract.py`
- Create: `lib/src/visual_consistency_contract.py`

**Interfaces:**
- Produces: `compile_scene_prompt(scene, style_contract, character_bible, aspect_ratio, negative_style_rules=None) -> dict`
- Produces: `validate_prompt_index(prompt_index, strict_character_required=False, soft_consistency_ack=False) -> dict`

- [ ] **Step 1: Write failing tests**

```python
def test_prompt_compiler_keeps_style_hash_stable_across_scene_actions():
    first = compile_scene_prompt({"scene_id": "s1", "action": "pushes open a gold elevator"}, style, bible, "16:9")
    second = compile_scene_prompt({"scene_id": "s2", "action": "stands in a hospital corridor"}, style, bible, "16:9")
    assert first["prompt_style_hash"] == second["prompt_style_hash"]
    assert "pushes open" in first["compiled_prompt"]
    assert "hospital corridor" in second["compiled_prompt"]

def test_prompt_index_blocks_mid_batch_style_hash_drift():
    report = validate_prompt_index({"entries": [entry("s1", "hash-a"), entry("s2", "hash-b")]})
    assert not report["ok"]
    assert "prompt_style_hash_drift" in report["blockers"]
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3.12 -m unittest tests.python.test_visual_consistency_contract -v`

Expected: import failure for `visual_consistency_contract`.

- [ ] **Step 3: Implement minimal helper**

Implement deterministic normalization, SHA-256 hash over stable blocks, prompt assembly, and prompt-index checks for missing final prompts, hash drift, fallback metadata, and strict-reference downgrade.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3.12 -m unittest tests.python.test_visual_consistency_contract -v`

Expected: all tests pass.

### Task 2: CLI Validator

**Files:**
- Create: `scripts/validate_visual_consistency.py`
- Modify: `package.json`
- Test: `tests/python/test_visual_consistency_contract.py`

**Interfaces:**
- Produces CLI: `python3.12 scripts/validate_visual_consistency.py --prompt-index <path> --output <path> [--strict-character-required] [--soft-consistency-ack]`

- [ ] **Step 1: Write failing CLI test**

```python
def test_cli_writes_failed_report_for_hash_drift(tmp_path):
    prompt_index = tmp_path / "prompt_index.json"
    prompt_index.write_text(json.dumps({"entries": [entry("s1", "hash-a"), entry("s2", "hash-b")]}), encoding="utf-8")
    output = tmp_path / "style_consistency_report.json"
    result = subprocess.run([...], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(output.read_text())["ok"] is False
```

- [ ] **Step 2: Run test to verify RED**

Run: `python3.12 -m unittest tests.python.test_visual_consistency_contract -v`

Expected: CLI script missing.

- [ ] **Step 3: Implement CLI**

Read prompt index JSON, call `validate_prompt_index`, write JSON report, exit `0` on ok and `1` on failed report.

- [ ] **Step 4: Add py_compile coverage**

Add `scripts/validate_visual_consistency.py` to `package.json` test script.

### Task 3: QA And Release Gates

**Files:**
- Create: `tests/python/test_style_consistency_release_gate.py`
- Modify: `scripts/score_video_quality.py`
- Modify: `scripts/release_checkpoint.py`

**Interfaces:**
- Produces: style report blocker with id `style_consistency_failed`.

- [ ] **Step 1: Write failing gate tests**

```python
def test_score_video_quality_blocks_failed_style_consistency_report():
    checks, _ = score_video_quality.build_check_results(..., manifest={"artifacts": [{"category": "style_consistency_report", "path": report_path}]})
    assert any(check["id"] == "style_consistency_failed" and check["severity"] == "blocker" for check in checks)

def test_release_checkpoint_blocks_failed_style_consistency_report():
    checkpoint = release_checkpoint.build_release_checkpoint(workspace)
    assert "style_consistency_failed" in checkpoint["blockers"]
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3.12 -m unittest tests.python.test_style_consistency_release_gate -v`

Expected: missing blocker.

- [ ] **Step 3: Implement shared report readers in each script**

Look for `qa/style_consistency_report.json`, manifest artifact category `style_consistency_report`, and path values ending in `style_consistency_report.json`. Convert failed reports into blocker checks.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3.12 -m unittest tests.python.test_style_consistency_release_gate -v`

Expected: all tests pass.

### Task 4: life_sim Contract Consumer

**Files:**
- Modify: `capsules/life_sim.capsule/contracts/runtime.yaml`
- Modify: `capsules/life_sim.capsule/contracts/input_schema.yaml`
- Modify: `capsules/life_sim.capsule/quality/rules.yaml`
- Modify: `capsules/life_sim.capsule/quality/release_gates.yaml`
- Modify: `capsules/life_sim.capsule/scripts/life_sim_executor.py`
- Modify: `tests/python/test_life_sim_opening_body_audio_contract.py`

**Interfaces:**
- Consumes config: `visual_consistency_contract`
- Produces dry-run check id: `visual_consistency_contract_required`

- [ ] **Step 1: Write failing `life_sim` contract test**

```python
def test_validate_contract_requires_visual_consistency_contract():
    checks = executor.validate_contract("首富千金的一生", {}, self._minimal_config())
    assert self._check_by_id(checks, "visual_consistency_contract_required")["ok"]
```

- [ ] **Step 2: Run test to verify RED**

Run: `python3.12 -m unittest tests.python.test_life_sim_opening_body_audio_contract.LifeSimOpeningBodyAudioContractTest.test_validate_contract_requires_visual_consistency_contract -v`

Expected: check id missing.

- [ ] **Step 3: Implement runtime YAML flags and executor validation**

Add `visual_consistency_contract` under runtime defaults and require fail-closed reference policy.

- [ ] **Step 4: Run test to verify GREEN**

Run the focused test again and confirm it passes.

### Task 5: Final Verification And Push

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python3.12 -m unittest tests.python.test_visual_consistency_contract tests.python.test_style_consistency_release_gate tests.python.test_life_sim_opening_body_audio_contract -v
```

- [ ] **Step 2: Run full Python tests**

Run:

```bash
python3.12 -m unittest discover -s tests/python -v
```

- [ ] **Step 3: Run npm test**

Run:

```bash
npm test
```

- [ ] **Step 4: Commit and push**

Run:

```bash
git status --short
git add -f docs/superpowers/specs/2026-07-02-style-consistency-contract-design.md docs/superpowers/plans/2026-07-02-style-consistency-contract.md
git add lib/src/visual_consistency_contract.py scripts/validate_visual_consistency.py scripts/score_video_quality.py scripts/release_checkpoint.py package.json capsules/life_sim.capsule/contracts/runtime.yaml capsules/life_sim.capsule/contracts/input_schema.yaml capsules/life_sim.capsule/quality/rules.yaml capsules/life_sim.capsule/quality/release_gates.yaml capsules/life_sim.capsule/scripts/life_sim_executor.py tests/python/test_visual_consistency_contract.py tests/python/test_style_consistency_release_gate.py tests/python/test_life_sim_opening_body_audio_contract.py
git commit -m "fix: enforce visual consistency contract"
git push -u origin fix/style-consistency-contract
```
