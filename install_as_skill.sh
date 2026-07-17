#!/usr/bin/env bash

# Capsule Cinema installer for Claude Code, Codex, and OpenClaw.
# Usage: bash install_as_skill.sh [--target auto|claude|codex|openclaw] [--yes] [--skip-deps]

set -euo pipefail

TARGET="auto"
ASSUME_YES="false"
SKIP_DEPS="false"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { printf '(i) %s\n' "$1"; }
ok() { printf '[OK] %s\n' "$1"; }
warn() { printf '(!) %s\n' "$1" >&2; }
fail() { printf '[X] %s\n' "$1" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: bash install_as_skill.sh [options]

Options:
  --target auto|claude|codex|openclaw  Agent target (default: auto)
  --yes                                Upgrade an existing installation without prompting
  --skip-deps                          Copy the skill without installing Python dependencies
  -h, --help                           Show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      [ "$#" -ge 2 ] || fail "--target requires a value"
      TARGET="$2"
      shift 2
      ;;
    --target=*) TARGET="${1#*=}"; shift ;;
    --yes|-y) ASSUME_YES="true"; shift ;;
    --skip-deps) SKIP_DEPS="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

case "$TARGET" in
  auto)
    if [ -n "${CODEX_HOME:-}" ]; then
      TARGET="codex"
    elif [ -d "$HOME/.claude" ]; then
      TARGET="claude"
    elif [ -d "$HOME/.codex" ]; then
      TARGET="codex"
    elif [ -d "$HOME/.openclaw" ]; then
      TARGET="openclaw"
    else
      TARGET="claude"
    fi
    ;;
  claude|codex|openclaw) ;;
  *) fail "Unsupported target: $TARGET (choose auto, claude, codex, or openclaw)" ;;
esac

case "$TARGET" in
  claude)
    INSTALL_DIR="$HOME/.claude/skills/capsule-cinema"
    AGENT_LABEL="Claude Code"
    ;;
  codex)
    INSTALL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/capsule-cinema"
    AGENT_LABEL="Codex"
    ;;
  openclaw)
    INSTALL_DIR="$HOME/.openclaw/skills/capsule-cinema"
    AGENT_LABEL="OpenClaw"
    ;;
esac

printf '\nCapsule Cinema — install\n\n'
info "Target agent: $AGENT_LABEL"
info "Install directory: $INSTALL_DIR"

if [ "$TARGET" = "openclaw" ] && [ -d "$HOME/skills/capsule-cinema" ]; then
  warn "A legacy OpenClaw install exists at $HOME/skills/capsule-cinema"
  warn "It will not be modified or migrated automatically; review any user-owned capsules, channels, output, and credentials separately."
fi

if [ -d "$INSTALL_DIR" ] && [ "$ASSUME_YES" != "true" ]; then
  printf 'The skill already exists. Upgrade it while preserving .env, local-channels, capsules, and output? [y/N] '
  read -r REPLY
  case "$REPLY" in
    y|Y|yes|YES) ;;
    *) info "Cancelled"; exit 0 ;;
  esac
fi

mkdir -p "$INSTALL_DIR"

# Overlay the public runtime while leaving user-owned credentials, local channels,
# capsules, and generated releases untouched on upgrades.
rsync -a \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='.pytest_cache' \
  --exclude='.worktrees' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='output' \
  --exclude='artifacts' \
  --exclude='reports' \
  --exclude='analysis_outputs' \
  --exclude='local-channels' \
  --exclude='local-capsules' \
  --exclude='private-capsules' \
  --exclude='lib/custom_tools/**/local_*_adapter*.py' \
  --exclude='lib/custom_tools/**/local_*_analyzer*.py' \
  --exclude='tests' \
  --exclude='skills/capsule-cinema' \
  "$SOURCE_DIR/" "$INSTALL_DIR/"

# All supported agents discover the standard uppercase entry. Move any legacy
# lowercase entry aside first so upgrades also work on case-insensitive filesystems.
STANDARD_SKILL="$SOURCE_DIR/skills/capsule-cinema/SKILL.md"
[ -f "$STANDARD_SKILL" ] || fail "Standard skill entry was not found: $STANDARD_SKILL"
if [ -f "$INSTALL_DIR/skill.md" ]; then
  mv "$INSTALL_DIR/skill.md" "$INSTALL_DIR/.capsule-cinema-legacy-skill.tmp"
fi
cp "$STANDARD_SKILL" "$INSTALL_DIR/SKILL.md"
mkdir -p "$INSTALL_DIR/agents"
cp "$SOURCE_DIR/skills/capsule-cinema/agents/openai.yaml" "$INSTALL_DIR/agents/openai.yaml"
rm -f "$INSTALL_DIR/.capsule-cinema-legacy-skill.tmp"

ok "Skill files installed"

if ! command -v python3.12 >/dev/null 2>&1; then
  fail "python3.12 was not found. Install Python 3.12, then rerun this installer."
fi

if [ "$SKIP_DEPS" = "true" ]; then
  warn "Skipped Python dependency installation"
else
  info "Installing Python dependencies (this can take a few minutes)"
  PIP_DISABLE_PIP_VERSION_CHECK=1 python3.12 -m pip install -r "$INSTALL_DIR/lib/requirements.txt"
  ok "Python dependencies installed"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  ok "FFmpeg found"
else
  warn "FFmpeg was not found. Install it before rendering, mixing audio, subtitles, or final video."
fi

PYTHONPATH="$INSTALL_DIR/lib" python3.12 "$INSTALL_DIR/scripts/capsule.py" list >/dev/null
ok "Capsule runtime smoke check passed"

printf '\nInstallation complete.\n'
printf '1. Configure credentials through agent/system environment variables, or copy:\n'
printf '   %s/lib/.env.example -> %s/.env\n' "$INSTALL_DIR" "$INSTALL_DIR"
printf '2. Never paste or commit secret values.\n'
printf '3. Restart %s so it discovers Capsule Cinema.\n' "$AGENT_LABEL"
printf '4. Then say: 用 Capsule Cinema 先为「一只橘猫深夜做饭」做 20 秒竖屏分镜，不要生成媒体。\n\n'
