#!/bin/bash

# Cancel Pickle Rick Script
# Sets the loop state to inactive

set -euo pipefail

EXTENSION_DIR="$HOME/.gemini/extensions/pickle-rick"
source "$EXTENSION_DIR/scripts/utils.sh"

# Resolve current project root
PROJECT_ROOT=$(resolve_project_root)

# Get session using the resolved root
SESSION_DIR=$("$EXTENSION_DIR/scripts/get_session.sh" "$PROJECT_ROOT" 2>/dev/null || true)

if [[ -z "$SESSION_DIR" ]]; then
  echo "❌ No active session found for current directory ($PWD -> $PROJECT_ROOT)" >&2
  exit 1
fi

STATE_FILE="$SESSION_DIR/state.json"

if [[ ! -f "$STATE_FILE" ]]; then
  echo "❌ No active Pickle Rick loop found" >&2
  echo "   State file not found: $STATE_FILE" >&2
  exit 1
fi

# Check CWD (Session Working Dir should match Project Root)
SESSION_CWD=$(jq -r '.working_dir // empty' "$STATE_FILE")
if [[ -n "$SESSION_CWD" ]]; then
  # Use physical paths for comparison to avoid symlink confusion
  PHYSICAL_ROOT=$(cd "$PROJECT_ROOT" && pwd -P 2>/dev/null || echo "$PROJECT_ROOT")
  PHYSICAL_SESSION_CWD=$(cd "$SESSION_CWD" && pwd -P 2>/dev/null || echo "$SESSION_CWD")

  if [[ "$PHYSICAL_ROOT" != "$PHYSICAL_SESSION_CWD" ]]; then
      echo "❌ Cancelling Pickle Rick failed: You are in a different project root ($PROJECT_ROOT) than the active session ($SESSION_CWD)." >&2
      exit 1
  fi
fi

# Update state file to set active: false
if [[ "$(uname)" == "Darwin" ]]; then
  # macOS sed requires empty string after -i
  sed -i '' 's/"active": true/"active": false/' "$STATE_FILE"
else
  # GNU sed
  sed -i 's/"active": true/"active": false/' "$STATE_FILE"
fi

echo "✅ Pickle Rick cancelled"
echo "State file: $STATE_FILE"