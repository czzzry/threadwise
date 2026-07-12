#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

print_header() {
  printf '\n== %s ==\n' "$1"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

find_agent_cli() {
  local cmd="$1"
  local fallback="$HOME/.local/bin/$cmd"
  if have_cmd "$cmd"; then
    command -v "$cmd"
  elif [ -x "$fallback" ]; then
    printf '%s\n' "$fallback"
  else
    return 1
  fi
}

print_header "Repo"
printf 'Root: %s\n' "$ROOT_DIR"

if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'Git: yes\n'
  printf 'Branch: %s\n' "$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || printf 'unknown')"
  printf 'Status:\n'
  git -C "$ROOT_DIR" status --short || true
else
  printf 'Git: no\n'
fi

print_header "Agent CLIs"
for cmd in codex hermes; do
  if cli_path="$(find_agent_cli "$cmd")"; then
    printf '%s: %s\n' "$cmd" "$cli_path"
  else
    printf '%s: not found\n' "$cmd"
  fi
done

print_header "Runtime Tools"
for cmd in python3 node npm pnpm yarn bun pytest; do
  if have_cmd "$cmd"; then
    printf '%s: %s\n' "$cmd" "$(command -v "$cmd")"
  else
    printf '%s: not found\n' "$cmd"
  fi
done

print_header "Package Files"
package_files=(
  "package.json"
  "pnpm-lock.yaml"
  "package-lock.json"
  "yarn.lock"
  "bun.lock"
  "bun.lockb"
  "pyproject.toml"
  "requirements.txt"
  "requirements-dev.txt"
  "Pipfile"
  "poetry.lock"
)

found_any_package_file=false
for rel in "${package_files[@]}"; do
  if [ -f "$ROOT_DIR/$rel" ]; then
    found_any_package_file=true
    printf '%s\n' "$rel"
  fi
done
if [ "$found_any_package_file" = false ]; then
  printf 'No top-level package manifest found.\n'
fi

print_header "Detected App Shape"
if [ -f "$ROOT_DIR/src/gmail_companion_ui.py" ]; then
  printf 'Backend/local server: src/gmail_companion_ui.py\n'
fi
if [ -f "$ROOT_DIR/scripts/run_gmail_companion.py" ]; then
  printf 'Main UI launcher: scripts/run_gmail_companion.py\n'
fi
if [ -f "$ROOT_DIR/scripts/review_local_batch_in_browser.py" ]; then
  printf 'Local review UI launcher: scripts/review_local_batch_in_browser.py\n'
fi
if [ -f "$ROOT_DIR/extensions/gmail_companion/manifest.json" ]; then
  printf 'Browser extension entry: extensions/gmail_companion/manifest.json\n'
fi

print_header "Likely Checks"
printf '%s\n' "python3 -m unittest discover -s tests"
printf '%s\n' "python3 scripts/check_operational_readiness.py"
printf '%s\n' "python3 scripts/run_gmail_companion.py --help"
printf '%s\n' "python3 scripts/review_local_batch_in_browser.py --help"

print_header "README Hints"
if [ -f "$ROOT_DIR/README.md" ]; then
  grep -E '^python3 scripts/' "$ROOT_DIR/README.md" || true
else
  printf 'README.md not found.\n'
fi

print_header "Docs And Instructions"
for rel in AGENTS.md .hermes.md README.md CONTEXT.md docs/hermes-codex-operating-model.md; do
  if [ -f "$ROOT_DIR/$rel" ]; then
    printf '%s\n' "$rel"
  fi
done

print_header "Notes"
printf '%s\n' "This script is read-only. It does not install tools, authenticate services, edit files, or run destructive commands."
