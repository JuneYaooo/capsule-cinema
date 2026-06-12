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
--params /abs/run/inputs/params.json
--output-dir /abs/run
```

`params.json` should contain the merged user inputs and capsule `config`. Do not pass secrets in params; use env vars.

## Required Outputs

The script must keep all files under the provided run directory and write:

```text
<run_dir>/
  final/
    video.mp4
    copy.txt
  reports/
    run_notes.json
  artifact_manifest.json
```

Minimum manifest:

```json
{
  "artifacts": [
    {"path": "/abs/run/final/video.mp4", "category": "final_video", "title": "Final video"},
    {"path": "/abs/run/final/copy.txt", "category": "copywriting", "title": "Copywriting"}
  ]
}
```

## Exit Behavior

- Exit `0` only when the final video and manifest were written.
- Exit non-zero when the run cannot produce a usable final artifact.
- Write concise failure notes to `reports/run_notes.json` when possible.
- Do not hide tool failures behind an empty placeholder video.

## QA And Feedback

After the local script runs:

```bash
python "scripts/local_video_qa.py" \
  --run-dir "$RUN_ROOT" \
  --aspect-ratio "9:16" \
  --expect-audio \
  --output "$RUN_ROOT/reports/local_video_qa.json"
```

Record the result:

```bash
python "scripts/capsule_store.py" record-run-dir \
  --name "<capsule>" \
  --run-dir "$RUN_ROOT" \
  --topic "<topic>" \
  --qa-report "$RUN_ROOT/reports/local_video_qa.json"
```

If QA fails, record feedback instead of promoting the capsule:

```bash
python "scripts/capsule_store.py" add-feedback \
  --name "<capsule>" \
  --type pitfall \
  --severity blocker \
  --summary "what failed" \
  --evidence "$RUN_ROOT/reports/local_video_qa.json" \
  --fix "what to change next"
```
