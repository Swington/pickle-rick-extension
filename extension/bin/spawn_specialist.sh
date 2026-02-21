#!/bin/bash

# Council of Ricks - Headless Specialist Spawner (Docker Mode + Vertex AI Auth)
# Usage: ./spawn_specialist.sh <specialist_type> "<task_description>"

TYPE=$1
TASK=$2
TIMESTAMP=$(date +%s)
AGENT_NAME="rick-${TYPE}-${TIMESTAMP}"
SESSION_DIR=$(cat "$HOME/.gemini/extensions/pickle-rick/current_sessions.json" | jq -r ".[\"$(pwd)\"]" 2>/dev/null || echo "$HOME/.gemini/tmp/council")
STATE_FILE="${SESSION_DIR}/council_state.json"
CHAT_FILE="${SESSION_DIR}/.council_chat.md"

mkdir -p "$SESSION_DIR"

if [[ -z "$TYPE" || -z "$TASK" ]]; then
    echo "❌ Error: Missing arguments."
    exit 1
fi

# 1. Initialize the Council Chat
if [[ ! -f "$CHAT_FILE" ]]; then
    echo "# Council of Ricks: Mission Log" > "$CHAT_FILE"
    echo "Mission started at $(date)" >> "$CHAT_FILE"
    echo "---" >> "$CHAT_FILE"
fi

# 2. Construct the Task Prompt
FINAL_TASK="POST YOUR INITIAL PLAN TO .council_chat.md IMMEDIATELY. REACH CONSENSUS. MISSION: $TASK"

# 3. Launch via Scion (Headless with Credentials)
# Mounting the host's gcloud config to the container
echo "Summoning $AGENT_NAME with Vertex AI access..."
scion start "$AGENT_NAME" "$FINAL_TASK" \
    --type rick \
    --harness-config gemini \
    --yes \
    --non-interactive \
    -w "$(pwd)" \
    --image us-central1-docker.pkg.dev/ptone-misc/public-docker/scion-gemini:latest

# 4. Record state
echo "{\"name\": \"$AGENT_NAME\", \"type\": \"$TYPE\", \"status\": \"active\"}" >> "${STATE_FILE}.tmp"
if command -v jq &> /dev/null; then
    jq -s '.' "${STATE_FILE}.tmp" > "$STATE_FILE" && rm "${STATE_FILE}.tmp"
fi

echo "SUCCESS: $AGENT_NAME is active and authenticated."
