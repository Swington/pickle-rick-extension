#!/bin/bash

# Council of Ricks - High-Reliability Specialist Spawner
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
TIMESTAMP=$(date +%s)
AGENT_NAME="rick-${TYPE}-${TIMESTAMP}"
SESSION_DIR=$(cat "$HOME/.gemini/extensions/pickle-rick/current_sessions.json" | jq -r '.latest_session_dir' 2>/dev/null || echo "$HOME/.gemini/tmp/council")
STATE_FILE="${SESSION_DIR}/council_state.json"

mkdir -p "$SESSION_DIR"

if [[ -z "$TMUX" ]]; then
    echo "❌ Error: Council of Ricks requires a tmux session."
    exit 1
fi

if [[ -z "$TYPE" || -z "$TASK" ]]; then
    echo "❌ Error: Missing arguments."
    exit 1
fi

# 1. Load Persona Content
EXTENSION_PATH="$HOME/.gemini/extensions/pickle-rick"
SYSTEM_PROMPT_FILE="$EXTENSION_PATH/.scion/templates/rick/home/system_prompt.md"
if [[ -f "$SYSTEM_PROMPT_FILE" ]]; then
    PERSONA_HEADER=$(cat "$SYSTEM_PROMPT_FILE")
else
    PERSONA_HEADER="# **SPECIALIST RICK**"
fi

case "$TYPE" in
    "research") PERSONA_SKILL="code-researcher" ;;
    "architect") PERSONA_SKILL="implementation-planner" ;;
    "dev") PERSONA_SKILL="code-implementer" ;;
    "auditor") PERSONA_SKILL="ruthless-refactorer" ;;
    *) PERSONA_SKILL="" ;;
esac

# 2. Construct the combined Task Prompt
FINAL_TASK=$(cat <<EOF
$PERSONA_HEADER

# **${TYPE^^} MISSION**
$TASK

1. Call activate_skill('load-pickle-persona')
$( [[ -n "$PERSONA_SKILL" ]] && echo "2. Call activate_skill('$PERSONA_SKILL')" )
3. Execute the task.
4. Output <promise>I AM DONE</promise> when finished.
EOF
)

# 3. Determine Layout
MANAGER_PANE_ID=$(tmux display-message -p '#{pane_id}')
NUM_PANES=$(tmux list-panes | wc -l)

if [ "$NUM_PANES" -eq 1 ]; then
    echo "🥒 Initializing Right Wing..."
    # Vertical split from manager
    NEW_PANE=$(tmux split-window -h -p 40 -P -F "#{pane_id}" -d -t "$MANAGER_PANE_ID")
else
    # Find the largest pane that is NOT the manager pane
    TARGET_PANE=$(tmux list-panes -F "#{pane_id} #{pane_height}" | grep -v "^${MANAGER_PANE_ID}" | sort -nr -k 2 | head -n 1 | awk '{print $1}')
    if [ -z "$TARGET_PANE" ]; then
        NEW_PANE=$(tmux split-window -v -P -F "#{pane_id}" -d)
    else
        echo "🥒 Slicing pane $TARGET_PANE..."
        NEW_PANE=$(tmux split-window -v -P -F "#{pane_id}" -d -t "$TARGET_PANE")
    fi
fi

# 4. Launch directly via split-window (Much more reliable than send-keys)
# We wrap in a subshell to keep the pane open after completion
LAUNCH_CMD="scion start \"$AGENT_NAME\" \"$FINAL_TASK\" --type rick --yes --attach; echo -e '\n\n🥒 Rick has finished his mission. Waiting for Manager termination...'; bash"

tmux send-keys -t "$NEW_PANE" "$LAUNCH_CMD" C-m

# 5. Record state for Manager
echo "{\"name\": \"$AGENT_NAME\", \"pane\": \"$NEW_PANE\", \"type\": \"$TYPE\", \"status\": \"active\"}" >> "${STATE_FILE}.tmp"
# Use jq to merge into a clean array if available, otherwise just append
if command -v jq &> /dev/null; then
    jq -s '.' "${STATE_FILE}.tmp" > "$STATE_FILE" && rm "${STATE_FILE}.tmp"
fi

echo "SUCCESS: $AGENT_NAME summoned in pane $NEW_PANE"
