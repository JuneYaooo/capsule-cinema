#!/usr/bin/env bash

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_URL="${CAPSULE_CINEMA_REPOSITORY_URL:-https://github.com/JuneYaooo/capsule-cinema.git}"
RUNTIME_REF="${CAPSULE_CINEMA_RUNTIME_REF:-main}"

is_runtime() {
  [ -f "$1/scripts/capsule.py" ] && [ -f "$1/lib/requirements.txt" ]
}

absolute_dir() {
  (cd "$1" && pwd)
}

if [ -n "${CAPSULE_CINEMA_HOME:-}" ]; then
  if ! is_runtime "$CAPSULE_CINEMA_HOME"; then
    printf 'CAPSULE_CINEMA_HOME is not a valid Capsule Cinema runtime: %s\n' "$CAPSULE_CINEMA_HOME" >&2
    exit 1
  fi
  absolute_dir "$CAPSULE_CINEMA_HOME"
  exit 0
fi

for candidate in "$SKILL_DIR" "$SKILL_DIR/../.." "$SKILL_DIR/runtime"; do
  if is_runtime "$candidate"; then
    absolute_dir "$candidate"
    exit 0
  fi
done

if ! command -v git >/dev/null 2>&1; then
  printf 'git is required to install the Capsule Cinema runtime.\n' >&2
  exit 1
fi

runtime_dir="${CAPSULE_CINEMA_RUNTIME_DIR:-$SKILL_DIR/runtime}"
if [ -e "$runtime_dir" ]; then
  printf 'Runtime target already exists but is incomplete: %s\n' "$runtime_dir" >&2
  printf 'Move it aside or set CAPSULE_CINEMA_RUNTIME_DIR to an empty path.\n' >&2
  exit 1
fi

mkdir -p "$(dirname "$runtime_dir")"
printf 'Installing Capsule Cinema runtime from %s at ref %s...\n' "$REPOSITORY_URL" "$RUNTIME_REF" >&2
git clone --depth 1 --branch "$RUNTIME_REF" "$REPOSITORY_URL" "$runtime_dir" >&2

if ! is_runtime "$runtime_dir"; then
  printf 'The cloned repository is missing required runtime files: %s\n' "$runtime_dir" >&2
  exit 1
fi

absolute_dir "$runtime_dir"
