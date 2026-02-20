#!/bin/bash

# Council of Ricks - Smart Layout Specialist Spawner
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

# Determine persona based on type
case "$TYPE" in
    "research") PERSONA_SKILL="code-researcher" ;;
    "architect") PERSONA_SKILL="implementation-planner" ;;
    "dev") PERSONA_SKILL="code-implementer" ;;
    "auditor") PERSONA_SKILL="ruthless-refactorer" ;;
    *) PERSONA_SKILL="" ;;
esac

# 1. Determine the best split strategy
NUM_PANES=$(tmux list-panes | wc -l)

if [ "$NUM_PANES" -eq 1 ]; then
    # First split: Vertical (panes side-by-side)
    # We take 40% of the width for the specialists
    echo "🥒 Initializing the Right Wing..."
    NEW_PANE=$(tmux split-window -h -p 40 -P -d)
else
    # Subsequent splits: Find the tallest pane on the right
    # We ignore panes at the far left (pane_at_left=1)
    TARGET_PANE=$(tmux list-panes -F "#{pane_id} #{pane_height} #{pane_at_left}" | grep " 0$" | sort -nr -k 2 | head -n 1 | awk '{print $1}')
    
    if [ -z "$TARGET_PANE" ]; then
        # Fallback if we can't find a right-side pane
        NEW_PANE=$(tmux split-window -v -P -d)
    else
        echo "🥒 Slicing pane $TARGET_PANE..."
        NEW_PANE=$(tmux split-window -v -t "$TARGET_PANE" -P -d)
    fi
fi

# 2. Setup Persona
PROMPT_FILE=$(mktemp /tmp/rick_prompt_XXXXXX.txt)
cat <<EOF > "$PROMPT_FILE"
# **${TYPE^^} RICK TASK**
$TASK

EOF

if [[ -n "$PERSONA_SKILL" ]]; then
cat <<EOF >> "$PROMPT_FILE"
1. Call activate_skill('$PERSONA_SKILL')
2. Execute the task.
3. Output <promise>I AM DONE</promise> when finished.
EOF
else
cat <<EOF >> "$PROMPT_FILE"
1. Execute the task.
2. Output <promise>I AM DONE</promise> when finished.
EOF
fi

# 3. Launch and Attach
CMD="gemini -s -y --include-directories \"$EXTENSION_PATH\" --system-prompt \"$SYSTEM_PROMPT_FILE\" -p \"$(cat $PROMPT_FILE)\"; rm -f $PROMPT_FILE; echo -e '\n\n🥒 Mission Accomplished. Closing in 5s...'; sleep 5"

tmux send-keys -t "$NEW_PANE" "$CMD" C-m
