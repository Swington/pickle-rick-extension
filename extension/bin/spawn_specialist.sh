#!/bin/bash

# Council of Ricks - Consensus-Enabled Specialist Spawner
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
TIMESTAMP=$(date +%s)
AGENT_NAME="rick-${TYPE}-${TIMESTAMP}"
SESSION_DIR=$(cat "$HOME/.gemini/extensions/pickle-rick/current_sessions.json" | jq -r '.latest_session_dir' 2>/dev/null || echo "$HOME/.gemini/tmp/council")
STATE_FILE="${SESSION_DIR}/council_state.json"
CHAT_FILE=".council_chat.md"

mkdir -p "$SESSION_DIR"

if [[ -z "$TMUX" ]]; then
    echo "❌ Error: Council of Ricks requires a tmux session."
    exit 1
fi

if [[ -z "$TYPE" || -z "$TASK" ]]; then
    echo "❌ Error: Missing arguments."
    exit 1
fi

# 1. Initialize the Council Chat if this is the first Rick
if [[ ! -f "$CHAT_FILE" ]]; then
    echo "# Council of Ricks: Mission Log" > "$CHAT_FILE"
    echo "Mission started at $(date)" >> "$CHAT_FILE"
    echo "---" >> "$CHAT_FILE"
fi

# 2. Load Persona Content
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
    "tester") PERSONA_SKILL="code-researcher" ;; # Use researcher for testing mapping
    *) PERSONA_SKILL="" ;;
esac

# 3. Construct the combined Task Prompt
FINAL_TASK=$(cat <<EOF
$PERSONA_HEADER

# **${TYPE^^} MISSION**
$TASK

**TEAM CONTEXT**: You are working with a Council of Ricks. Use '.council_chat.md' to coordinate.
Your Agent Name is: $AGENT_NAME

1. Call activate_skill('load-pickle-persona')
$( [[ -n "$PERSONA_SKILL" ]] && echo "2. Call activate_skill('$PERSONA_SKILL')" )
3. POST YOUR INITIAL PLAN TO .council_chat.md IMMEDIATELY.
4. REVIEW PEERS AND REACH CONSENSUS.
5. Execute the task once consensus is reached.
6. Output <promise>I AM DONE</promise> when finished.
EOF
)

# 4. Determine Layout
MANAGER_PANE_ID=$(tmux display-message -p '#{pane_id}')
NUM_PANES=$(tmux list-panes | wc -l)

if [ "$NUM_PANES" -eq 1 ]; then
    echo "🥒 Initializing Right Wing..."
    NEW_PANE=$(tmux split-window -h -p 40 -P -F "#{pane_id}" -d -t "$MANAGER_PANE_ID")
else
    TARGET_PANE=$(tmux list-panes -F "#{pane_id} #{pane_height}" | grep -v "^${MANAGER_PANE_ID}" | sort -nr -k 2 | head -n 1 | awk '{print $1}')
    if [ -z "$TARGET_PANE" ]; then
        NEW_PANE=$(tmux split-window -v -P -F "#{pane_id}" -d)
    else
        echo "🥒 Slicing pane $TARGET_PANE..."
        NEW_PANE=$(tmux split-window -v -P -F "#{pane_id}" -d -t "$TARGET_PANE")
    fi
fi

# 5. Launch via Scion
LAUNCH_CMD="scion start \"$AGENT_NAME\" \"$FINAL_TASK\" --type rick --yes --attach; echo -e '\n\n🥒 Rick has finished his mission. Waiting for Manager review.'; bash"
tmux send-keys -t "$NEW_PANE" "$LAUNCH_CMD" C-m

# 6. Record state
echo "{\"name\": \"$AGENT_NAME\", \"pane\": \"$NEW_PANE\", \"type\": \"$TYPE\", \"status\": \"active\"}" >> "${STATE_FILE}.tmp"
if command -v jq &> /dev/null; then
    jq -s '.' "${STATE_FILE}.tmp" > "$STATE_FILE" && rm "${STATE_FILE}.tmp"
fi

echo "SUCCESS: $AGENT_NAME summoned in pane $NEW_PANE"
