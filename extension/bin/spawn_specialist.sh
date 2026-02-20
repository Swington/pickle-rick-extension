#!/bin/bash

# Council of Ricks - Fixed Spawner (Containerized + Smart Layout + Auto-Close)
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
TIMESTAMP=$(date +%s)
AGENT_NAME="rick-${TYPE}-${TIMESTAMP}"
EXTENSION_PATH="$HOME/.gemini/extensions/pickle-rick"
SYSTEM_PROMPT_FILE="$EXTENSION_PATH/.scion/templates/rick/home/system_prompt.md"

if [[ -z "$TMUX" ]]; then
    echo "❌ Error: Council of Ricks requires a tmux session."
    exit 1
fi

if [[ -z "$TYPE" || -z "$TASK" ]]; then
    echo "❌ Error: Missing arguments."
    exit 1
fi

# 1. Load Persona Content
if [[ -f "$SYSTEM_PROMPT_FILE" ]]; then
    PERSONA_HEADER=$(cat "$SYSTEM_PROMPT_FILE")
else
    PERSONA_HEADER="# **SPECIALIST RICK**"
fi

# Determine persona skill based on type
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

# 3. Determine the best split strategy
NUM_PANES=$(tmux list-panes | wc -l)

if [ "$NUM_PANES" -eq 1 ]; then
    echo "🥒 Initializing Right Wing..."
    NEW_PANE=$(tmux split-window -h -p 40 -P -d)
else
    TARGET_PANE=$(tmux list-panes -F "#{pane_id} #{pane_height} #{pane_at_left}" | grep " 0$" | sort -nr -k 2 | head -n 1 | awk '{print $1}')
    if [ -z "$TARGET_PANE" ]; then
        NEW_PANE=$(tmux split-window -v -P -d)
    else
        echo "🥒 Slicing pane $TARGET_PANE..."
        NEW_PANE=$(tmux split-window -v -t "$TARGET_PANE" -P -d)
    fi
fi

# 4. Launch via Scion and Auto-Close
# We use --attach so the scion process stays alive until the agent finishes.
# The '&& exit' ensures the tmux pane closes immediately after.
SCION_CMD="scion start \"$AGENT_NAME\" \"$FINAL_TASK\" --type rick --yes --attach; echo -e '\n\n🥒 Rick has finished his mission. Closing portal in 5s...'; sleep 5; exit"

tmux send-keys -t "$NEW_PANE" "$SCION_CMD" C-m
