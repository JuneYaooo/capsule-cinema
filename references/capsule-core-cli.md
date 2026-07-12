# Capsule Core CLI

`scripts/capsule.py` is the local creator surface for all repository-tracked v1 capsule packages. It discovers, explains, diagnoses, plans, and runs a capsule without asking whether the package uses a preset or a local runner.

## Discover and inspect

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py list
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py show art_motion
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py doctor art_motion
```

After argument parsing succeeds, each requested operation writes exactly one JSON result envelope to stdout with `ok`, `status`, `data`, and `issues`. An issue contains a stable `code`, human message, subject, remediation, severity, and optional details.

The process uses exit code `0` for a successful operation and exit code `1` for an operational or validation failure represented by that JSON envelope. An argparse syntax error or missing required CLI argument instead prints usage diagnostics to stderr, exits with exit code `2`, and stdout remains empty.

## Plan through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py plan art_motion \
  --topic "Ink flowers opening into a summer landscape" \
  --params-json '{"aspect_ratio":"9:16"}' \
  --output-dir output/art-motion-plan
```

`plan` validates and prepares dispatch but does not claim that a deliverable video exists. The same command works for every runner family.

## Run through one interface

```bash
PYTHONPATH=lib:scripts python3.12 scripts/capsule.py run felt_asmr \
  --topic "A wool-felt strawberry mille-feuille" \
  --params-json '{"target_duration":20,"aspect_ratio":"9:16"}' \
  --output-dir output/felt-asmr-run
```

The command delegates to the existing production runner. The unified CLI forwards legacy runner logs to stderr and reserves stdout for the final JSON envelope; produced artifacts retain their current contracts.

## Foundation boundary

This compatibility layer does not rewrite v1 packages. Native definitions, configured instances, macro controls, Production Blocks, compiled stage contexts, release locks, run evidence, and lesson proposals are introduced by subsequent core plans.
