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

# 1. Start the agent in a detached container using Scion
# We use the 'rick' template which has our persona already baked in.
echo "🥒 Summoning $AGENT_NAME from the multi-verse..."
scion start "$AGENT_NAME" "$TASK" --type rick --yes

# 2. Split the current tmux window and attach to the container
# This gives the user the visual 'teammate' experience.
echo "🥒 Opening a portal to $AGENT_NAME's brain..."
tmux split-window -h "scion attach $AGENT_NAME"
