#!/bin/bash
# Returns the session path for the current working directory (or provided path).

set -euo pipefail

EXTENSION_DIR="$HOME/.gemini/extensions/pickle-rick"
SESSIONS_MAP="$EXTENSION_DIR/current_sessions.json"

# Source utils for path resolution
source "$EXTENSION_DIR/scripts/utils.sh"

TARGET_DIR="${1:-$PWD}"

if [[ ! -f "$SESSIONS_MAP" ]]; then
  exit 1
fi

# Resolve the Project Root for the target directory
# We use a subshell to avoid changing the main script's PWD
PROJECT_ROOT=$(cd "$TARGET_DIR" && resolve_project_root)

# Find exact match for PROJECT_ROOT
SESSION_PATH=$(jq -r --arg cwd "$PROJECT_ROOT" '.[$cwd] // empty' "$SESSIONS_MAP")

if [[ -n "$SESSION_PATH" ]]; then
  echo "$SESSION_PATH"
else
  exit 1
fi
