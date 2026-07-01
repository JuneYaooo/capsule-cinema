# Local Script Protocol

Use this only for mature local workflows where a script or folder is more reliable than agent-driven step-by-step generation. The local script is not a remote package and should not require cloud storage.

## Contract

A `local_script` capsule stores:

```json
{
  "execution_mode": "local_script",
  "local_script_path": "/abs/project/capsules/name/main.py",
  "input_schema": {
    "topic": {"type": "string", "required": true}
  },
  "quality_rules": []
}
```

## Inputs

The script should accept:

```bash
--topic "..."
--params /abs/project/output/<run_id>/inputs/params.json
--output-dir /abs/project/output/<run_id>
```

`params.json` should contain the merged user inputs and capsule `config`. Do not pass secrets in params; use env vars.

## Required Outputs

The script must keep all files under the provided run directory and write:

```text
<run_dir>/
  release/
    video.mp4
    copy.txt
  qa/
    run_notes.json
  artifact_manifest.json
```

Minimum manifest:

```json
{
  "artifacts": [
    {"path": "/abs/project/output/<run_id>/release/video.mp4", "category": "final_video", "title": "Final video"},
    {"path": "/abs/project/output/<run_id>/release/copy.txt", "category": "copywriting", "title": "Copywriting"}
  ]
}
```

## Exit Behavior

- Exit `0` only when the final video and manifest were written.
- Exit non-zero when the run cannot produce a usable final artifact.
- Write concise failure notes to `qa/run_notes.json` when possible.
- Do not hide tool failures behind an empty placeholder video.

## QA And Feedback

After the local script runs:

```bash
python "scripts/local_video_qa.py" \
  --run-dir "$RUN_ROOT" \
  --aspect-ratio "9:16" \
  --expect-audio \
  --output "$RUN_ROOT/qa/local_video_qa.json"
```

Review the QA result before touching the active package. If the run reveals a reusable fix, promote only the generalized lesson with `scripts/capsule_package_update.py`; keep run-specific evidence under the run root.

```bash
python "scripts/capsule_package_update.py" "capsules/<capsule>.capsule" \
  --lesson-id "<stable_lesson_id>" \
  --lesson-scope "quality" \
  --lesson-rule "Generalized fix to apply next time." \
  --applies-when "<trigger condition>"
```

If QA fails and the issue is not yet a stable reusable rule, leave it in `qa/run_notes.json`, `qa/repair_plan.json`, or the release checkpoint instead of promoting the capsule.
