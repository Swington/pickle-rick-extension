#!/bin/bash

# Council of Ricks - Parallel Specialist Spawner
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
EXTENSION_PATH="$HOME/.gemini/extensions/pickle-rick"
SYSTEM_PROMPT_FILE="$EXTENSION_PATH/.scion/templates/rick/home/system_prompt.md"

if [[ -z "$TMUX" ]]; then
    echo "❌ Error: Council of Ricks requires a tmux session."
    echo "Please start tmux first, then run your command."
    exit 1
fi

if [[ -z "$TYPE" || -z "$TASK" ]]; then
    echo "❌ Error: Missing arguments."
    echo "Usage: $0 <specialist_type> \"<task_description>\""
    exit 1
fi

# Determine persona based on type
case "$TYPE" in
    "research")
        PERSONA_SKILL="code-researcher"
        ;;
    "architect")
        PERSONA_SKILL="implementation-planner"
        ;;
    "dev")
        PERSONA_SKILL="code-implementer"
        ;;
    "auditor")
        PERSONA_SKILL="ruthless-refactorer"
        ;;
    *)
        PERSONA_SKILL=""
        ;;
esac

TITLE="Rick ($TYPE)"

# Split the current pane and run Gemini
NEW_PANE=$(tmux split-window -h -P -d)

# Set the pane border color/title (if supported by user's tmux config)
tmux select-pane -t "$NEW_PANE" -T "$TITLE" 2>/dev/null || true

# Create a temporary file for the prompt to avoid quoting nightmares
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

# Construct the command to run in the new pane
CMD="gemini -s -y --include-directories \"$EXTENSION_PATH\" --system-prompt \"$SYSTEM_PROMPT_FILE\" -p \"
$(cat $PROMPT_FILE)\"; rm -f $PROMPT_FILE"

# Send the command to the new pane and press Enter
tmux send-keys -t "$NEW_PANE" "$CMD" C-m
