#!/bin/bash
# -----------------------------------------------------------------------------
# Pickle Rick: Universal Installer
# -----------------------------------------------------------------------------
# Deploys the Pickle Rick extension to a target directory.
# Automatically patches paths to ensure functionality in the new dimension.
# -----------------------------------------------------------------------------

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${1:-}"

if [[ -z "$TARGET_ROOT" ]]; then
  echo "Usage: $0 <target_directory>"
  echo "Example: $0 ~/.gemini/antigravity"
  exit 1
fi

TARGET_EXT_DIR="$TARGET_ROOT/extensions/pickle-rick"

echo "🥒 Installing Pickle Rick to: $TARGET_EXT_DIR"

# 1. Create Target Directory
if [[ -d "$TARGET_EXT_DIR" ]]; then
  echo "⚠️  Target exists. Overwriting..."
  rm -rf "$TARGET_EXT_DIR"
fi
mkdir -p "$TARGET_EXT_DIR"

# 2. Copy Files
echo "📦 Copying payload..."
cp -R "$SOURCE_DIR/"* "$TARGET_EXT_DIR/"

# 3. Clean Session History (Don't copy my garbage)
echo "🧹 Sanitizing history..."
rm -rf "$TARGET_EXT_DIR/sessions/"*
rm -rf "$TARGET_EXT_DIR/worktrees/"*
rm -f "$TARGET_EXT_DIR/current_sessions.json"
rm -f "$TARGET_EXT_DIR/state.json"
mkdir -p "$TARGET_EXT_DIR/sessions"
mkdir -p "$TARGET_EXT_DIR/worktrees"

# 4. Patch Paths
echo "🔧 Patching quantum coordinates..."
# We need to replace the source path (likely ~/.gemini/extensions/pickle-rick) 
# with the target path.
# However, we can't assume the source path. We should look for the *pattern*
# ".gemini/extensions/pickle-rick" and replace it with the relative path of the target.

# Determine the "namespace" of the target.
# If target is ~/.gemini/antigravity, we want .gemini/antigravity/extensions/pickle-rick
# If target is ~/.antigravity, we want .antigravity/extensions/pickle-rick

# Simplify: Just find the literal string ".gemini/extensions/pickle-rick" and replace it
# with the absolute path of the target extension dir (relative to $HOME is cleaner if possible, but absolute is safer).

# Actually, let's use the absolute path $TARGET_EXT_DIR, but replaced with $HOME variable for portability if possible.
# But for now, absolute paths are fine.

# Replace .gemini/extensions/pickle-rick with the new suffix
# We assume the code uses ~/.gemini/extensions/pickle-rick or $HOME/.gemini/extensions/pickle-rick
# We will replace `.gemini/extensions/pickle-rick` with the tail of the target path relative to user home.

# Get path relative to home
TARGET_REL_HOME="${TARGET_EXT_DIR#$HOME/}"
# Ensure it doesn't start with /
TARGET_REL_HOME="${TARGET_REL_HOME#/}"

echo "   Target relative path: $TARGET_REL_HOME"

find "$TARGET_EXT_DIR" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.ps1" -o -name "*.toml" -o -name "*.txt" \) -print0 | xargs -0 sed -i '' "s|\.gemini/extensions/pickle-rick|$TARGET_REL_HOME|g"

# 5. Make Executable
chmod +x "$TARGET_EXT_DIR/scripts/"*.sh
chmod +x "$TARGET_EXT_DIR/hooks/"*.sh

echo "✅ Installation Complete. Wubba Lubba Dub Dub!"
