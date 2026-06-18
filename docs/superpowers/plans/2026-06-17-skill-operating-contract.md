# Skill Operating Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a test-protected operating contract to Capsule Cinema's agent-facing skill documentation.

**Architecture:** This is a documentation-contract change with static tests. `tests/skill.test.js` locks in the required skill and production-guide gates; `skill.md`, `references/production-guide.md`, and `account-distillation/SKILL.md` provide the agent-facing text. Runtime behavior stays unchanged.

**Tech Stack:** Node test harness, Markdown skill files, OpenClaw skill metadata.

## Global Constraints

- This change does not add new video generation workflows, new providers, new capsule schemas, or new runtime behavior.
- Root `skill.md` must add a short agent operating contract near the start of the body.
- `references/production-guide.md` must tighten route, policy, production, and release gates into superpower-style mandatory flow.
- `account-distillation/SKILL.md` frontmatter description must be trigger-only discovery text.
- Skill/capsule tests must preserve the operating contract and prevent future regressions.
- Existing `npm test` must continue to pass.

---

### Task 1: Skill Operating Contract Documentation

**Files:**
- Modify: `tests/skill.test.js`
- Modify: `skill.md`
- Modify: `references/production-guide.md`
- Modify: `account-distillation/SKILL.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-06-17-skill-operating-contract-design.md`
- Produces: `testSkillOperatingContractDocs()` in `tests/skill.test.js`
- Produces: `## Agent Operating Contract` in `skill.md`
- Produces: `## Iron Laws` in `references/production-guide.md`
- Produces: trigger-only `description:` in `account-distillation/SKILL.md`

- [ ] **Step 1: Add a frontmatter helper for skill-document tests**

In `tests/skill.test.js`, add this helper after `loadCapsulePackageManifest(name)`:

```javascript
function extractFrontmatterField(content, fieldName, sourceName) {
  const frontmatter = content.match(/^---\n([\s\S]*?)\n---/);
  assert.ok(frontmatter, `${sourceName} 应包含 YAML frontmatter`);
  const fieldPattern = new RegExp(`^${fieldName}:\\s*(.*)$`, 'm');
  const field = frontmatter[1].match(fieldPattern);
  assert.ok(field, `${sourceName} frontmatter 应包含 ${fieldName}`);
  return field[1].trim().replace(/^["']|["']$/g, '');
}
```

- [ ] **Step 2: Add the failing operating-contract test**

In `tests/skill.test.js`, add this test function after `testRuntimeTraceabilityArtifacts()`:

```javascript
// 测试 22: agent-facing skill 文档应保留 superpower 风格的操作契约
function testSkillOperatingContractDocs() {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const productionGuide = readFileSync(join(SKILL_DIR, 'references', 'production-guide.md'), 'utf-8');
  const accountDistillation = readFileSync(join(SKILL_DIR, 'account-distillation', 'SKILL.md'), 'utf-8');

  assert.ok(skillContent.includes('## Agent Operating Contract'), 'skill.md 应包含 Agent Operating Contract');
  assert.ok(
    skillContent.includes('read `references/production-guide.md` before planning'),
    'skill.md 应要求视频制作前读取 production guide'
  );
  assert.ok(
    skillContent.includes('inspect the local SQLite capsule contract with `scripts/capsule_store.py show <name> --contract` before planning'),
    'skill.md 应要求胶囊任务先检查 SQLite 胶囊合同'
  );
  assert.ok(
    skillContent.includes('choose tools only after reading the active channel policy and `lib/config/tool_registry.yaml`'),
    'skill.md 应要求按 channel policy 和 tool registry 选择工具'
  );
  assert.ok(
    skillContent.includes('do not describe the run as complete'),
    'skill.md 应禁止有 blocker 时声称完成'
  );

  assert.ok(productionGuide.includes('## Iron Laws'), 'production-guide 应包含 Iron Laws');
  for (const law of [
    'NO FINAL VIDEO DELIVERY WITHOUT A RELEASE CHECKPOINT',
    'NO UNAPPROVED CHANNEL FALLBACK',
    'NO REFERENCE REMAKE WITHOUT SOURCE ANALYSIS',
    'NO CAPSULE PLANNING WITHOUT CONTRACT INSPECTION',
  ]) {
    assert.ok(productionGuide.includes(law), `production-guide 应包含铁律: ${law}`);
  }

  const description = extractFrontmatterField(accountDistillation, 'description', 'account-distillation/SKILL.md');
  assert.ok(description.startsWith('Use when'), 'account-distillation description 应以 Use when 开头');
  for (const workflowVerb of ['Scout', 'Snapshot', 'Score', 'Synthesize', 'Codify']) {
    assert.ok(
      !description.includes(workflowVerb),
      `account-distillation description 不应总结工作流: ${workflowVerb}`
    );
  }

  console.log('  ✅ skill 操作契约文档验证通过');
}
```

In the `tests` array near the bottom of `tests/skill.test.js`, add this entry after `['运行时可追溯产物', testRuntimeTraceabilityArtifacts],`:

```javascript
  ['skill 操作契约文档', testSkillOperatingContractDocs],
```

- [ ] **Step 3: Run the test and verify it fails for the expected reason**

Run:

```bash
node tests/skill.test.js
```

Expected result: the command exits non-zero and reports that `skill.md` does not yet contain `Agent Operating Contract`.

If the command fails earlier for an unrelated reason, stop and inspect the earlier failure before editing docs.

- [ ] **Step 4: Add the root skill operating contract**

In `skill.md`, insert this section immediately after the frontmatter closing `---` and before `## 当前边界`:

```markdown
## Agent Operating Contract

Before planning or running tools, classify the request and read `references/production-guide.md` before planning for video-production routing. Use the runtime only within the workflows registered in this package.

- Route first: choose post-production, reference remake, capsule, new AI video, action transfer, digital human/lip sync, music MV, or blocker before writing prompts.
- Capsule first: for capsule tasks, inspect the local SQLite capsule contract with `scripts/capsule_store.py show <name> --contract` before planning.
- Policy first: choose tools only after reading the active channel policy and `lib/config/tool_registry.yaml`; never fall back to an unapproved provider.
- Prototype first: for new AI video, generate and inspect one representative hard scene before batching.
- Release first: final deliverables must stay under `output/` and include `artifact_manifest.json`, QA reports, repair plan when needed, and `release/release_checkpoint.json`.
- Blockers are honest output: if route, channel, asset, QA, EditPlan validation, visible copy lint, or release checkpoint blocks delivery, fix it or report it; do not describe the run as complete.
```

- [ ] **Step 5: Add iron laws and route-gate language to the production guide**

In `references/production-guide.md`, insert this section after the four-layer Design list and before the current route-scope paragraph:

````markdown
## Iron Laws

```text
NO FINAL VIDEO DELIVERY WITHOUT A RELEASE CHECKPOINT
NO UNAPPROVED CHANNEL FALLBACK
NO REFERENCE REMAKE WITHOUT SOURCE ANALYSIS
NO CAPSULE PLANNING WITHOUT CONTRACT INSPECTION
```

- A final delivery needs `release/release_checkpoint.json`; if the checkpoint is blocked, repair or report the blocker.
- Use only tools approved by the active channel policy and present in `lib/config/tool_registry.yaml`.
- Reference remakes must analyze the source video, image, link, or provided material before planning the new video.
- Capsule work must inspect the local SQLite contract with `scripts/capsule_store.py show <name> --contract` before planning.
````

Then rename the `## First Decision` heading to:

```markdown
## Route Gate
```

Replace the line `Before planning, classify the task:` with:

```markdown
Before planning, classify the task. If none of these routes can satisfy the request with approved tools and accessible local assets, report a blocker instead of forcing a generic run:
```

In the Channel Policy section, replace this sentence:

```markdown
When an approved generation channel fails, either retry within the same channel, use another channel that is explicitly approved in the current policy, use a non-generative editing fallback such as Ken Burns/real material, or report the blocker. Do not silently switch to an unapproved channel.
```

With this sentence:

```markdown
When an approved generation channel fails, either retry within the same channel, use another channel that is explicitly approved in the current policy, use a non-generative editing fallback such as Ken Burns/real material, or report the blocker. Unapproved channel fallback is a blocker; do not silently switch to an unapproved channel.
```

- [ ] **Step 6: Rewrite account-distillation discovery metadata**

In `account-distillation/SKILL.md`, replace the current `description:` line with:

```yaml
description: Use when the user asks to find or compare benchmark social-media accounts, research AI-news/AI-tools/AI-open-source creators, analyze high-performing posts, inspect hooks/openings/cover copy/video structure with TikHub or platform data, or build competitor-grounded self-media strategy. Chinese triggers: 蒸馏账号, 对标账号, 自媒体账号蒸馏, 爆款内容分析, 高赞内容, 高互动内容, 钩子结构, 开头钩子, 封面文案, AI新闻账号, AI工具账号, AI开源账号, TikHub搜索账号.
```

Leave the body workflow method unchanged.

- [ ] **Step 7: Run the targeted JS test and verify it passes**

Run:

```bash
node tests/skill.test.js
```

Expected result: the command exits `0`, and the output includes:

```text
✅ skill 操作契约文档验证通过
```

- [ ] **Step 8: Run the full repository verification**

Run:

```bash
npm test
```

Expected result: the command exits `0`. This runs the Node skill tests, Python unit tests, and Python compile checks declared in `package.json`.

- [ ] **Step 9: Check formatting and review the diff**

Run:

```bash
git diff --check
git diff -- tests/skill.test.js skill.md references/production-guide.md account-distillation/SKILL.md
```

Expected result: `git diff --check` exits `0`. Review the diff and confirm only the four planned files changed.

- [ ] **Step 10: Commit the implementation**

Run:

```bash
git add tests/skill.test.js skill.md references/production-guide.md account-distillation/SKILL.md
git commit -m "docs: add skill operating contract"
```

Expected result: git creates one commit containing the static test and the matching documentation changes.
