#!/bin/bash

# Council of Ricks - Parallel Containerized Specialist Spawner
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
TIMESTAMP=$(date +%s)
AGENT_NAME="rick-${TYPE}-${TIMESTAMP}"

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

# 1. Start and Attach in a new tmux pane
# We wrap it in a bash subshell so we can sleep before the pane closes,
# giving the user a chance to see the 'I AM DONE' promise.
echo "🥒 Summoning $AGENT_NAME..."
tmux split-window -h "bash -c 'scion start $AGENT_NAME \"$TASK\" --type rick --yes --attach; echo -e \"\n\n🥒 Rick has finished his mission. Closing pane in 5s...\"; sleep 5'"
