#!/bin/bash

# Council of Ricks - War Room (Monitoring Dashboard)

set -e

# Check for tmux
if ! command -v tmux &> /dev/null; then
    echo "❌ Error: tmux is not installed. Required for the War Room."
    exit 1
fi

SESSION_NAME="war_room_$(date +%s)"

# Create a new tmux session in detached mode
tmux new-session -d -s "$SESSION_NAME" -n "Dashboard"

# Set up the main dashboard view
tmux send-keys -t "$SESSION_NAME:Dashboard" "watch -n 1 'scion list --all'" C-m

# Create a second window for logs or active terminal
tmux new-window -t "$SESSION_NAME" -n "Logs"
tmux send-keys -t "$SESSION_NAME:Logs" "tail -f ~/.scion/logs/*.log 2>/dev/null || echo 'No logs found yet.'" C-m

# Open the tmux session
tmux attach-session -t "$SESSION_NAME"
