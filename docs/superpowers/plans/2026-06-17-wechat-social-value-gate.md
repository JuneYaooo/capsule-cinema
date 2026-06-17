# WeChat Social Value Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a general WeChat Channels social-value gate to the `github_skills_showcase` capsule.

**Architecture:** This is a capsule-contract change. The package manifest gains method and QA rules; the local render script remains unchanged because it renders agent-supplied profiles rather than selecting publishing angles.

**Tech Stack:** Node test harness, packaged `.capsule.zip` manifest JSON, Python zip update helper.

## Global Constraints

- Prioritize title and body copy; in-video title and bottom cards are weakly influenced only when project facts support it.
- Main default angle is distinctive viewpoint plus user value.
- Do not hard-code concrete example angles as universal rules.
- Do not expose internal method names in public copy.
- Claims must remain source-grounded.

---

### Task 1: Capsule Contract Rule

**Files:**
- Modify: `tests/skill.test.js`
- Modify: `capsules/github_skills_showcase.capsule.zip`

**Interfaces:**
- Consumes: `capsules/github_skills_showcase.capsule.zip` containing `manifest.json`.
- Produces: `.capsule.method.wechat_social_value_gate` and matching `quality_rules` entries.

- [x] **Step 1: Write the failing test**

Add a test that extracts `manifest.json` from the capsule zip and asserts:

- `method.wechat_social_value_gate` exists.
- `primary_angle` is `distinctive_view_with_user_value`.
- value angles include `hard_value`, `distinctive_view`, and `unexpected_use`.
- social behaviors include `like_signal` and `share_target`.
- quality rules include `wechat_social_value_gate_required`, `wechat_no_generic_interaction_copy`, and `wechat_abstract_methodology_boundary`.
- the new method block does not contain sample-specific tokens such as `Token`, `Agent`, `代码质量`, or `团队流程`.

- [x] **Step 2: Run test to verify it fails**

Run: `node tests/skill.test.js`

Expected: failure because the current capsule manifest has no `wechat_social_value_gate`.

- [x] **Step 3: Update capsule manifest**

Unpack the current zip, update only `manifest.json`, preserve packaged asset/script files, and write a new zip at `capsules/github_skills_showcase.capsule.zip`.

- [x] **Step 4: Run test to verify it passes**

Run: `node tests/skill.test.js`

Expected: all JS skill tests pass.

- [x] **Step 5: Run capsule doctor**

Run: `rm -f /tmp/capsule-cinema-check.sqlite && VIDEO_PRODUCTION_CAPSULE_DB=/tmp/capsule-cinema-check.sqlite python3 scripts/capsule_store.py import capsules/github_skills_showcase.capsule.zip --name github_skills_showcase_check --assets-dir /tmp/capsule-cinema-check-assets --force`

Expected: imported capsule passes package validation and doctor.
