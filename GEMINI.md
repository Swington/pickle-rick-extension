# Pickle Rick Extension

This directory contains the source code for the **Pickle Rick** extension for Gemini.

## Project Overview

The extension transforms the Gemini CLI into "Pickle Rick" (from Rick and Morty) - a hyper-intelligent, arrogant, but extremely competent coding agent. It emphasizes strict obedience, "God Mode" coding practices (inventing tools vs. using libraries), and a disdain for "AI Slop" (boilerplate).

It implements a rigid, iterative engineering lifecycle: **PRD -> Breakdown -> Research -> Plan -> Implement -> Refactor**.

## Key Components

### 1. Configuration
- **`gemini-extension.json`**: The main manifest file defining the extension name (`pickle-rick`) and context file (`GEMINI.md`).

### 2. Persona Definition
- **`hooks/reinforce-persona.sh`**: The core personality enforcer. It defines:
  - **Voice & Tone:** Cynical, manic, arrogant compliance ("I'm Pickle Rick! 🥒").
  - **Philosophy:** "God Complex" (create dependencies), "Anti-Slop" (optimize aggressively), "Malicious Competence" (over-deliver).
  - **The Prime Directive:** "Shut Up and Compute".

### 3. Commands
The extension exposes the following commands via TOML definitions in `commands/`:

- **`/pickle`** (`commands/pickle.toml`):
  - **Purpose:** Initiates the iterative development loop.
  - **Implementation:** Maps to `scripts/setup.sh`.
  - **Usage:** `/pickle <prompt> [--max-iterations N] [--completion-promise 'text'] [--resume [PATH]]`

- **`/pickle-prd`** (`commands/pickle-prd.toml`):
  - **Purpose:** Interactively drafts a PRD and initializes a session.
  - **Usage:** `/pickle-prd <prompt>`
  
- **`/eat-pickle`** (`commands/eat-pickle.toml`):
  - **Purpose:** Cancels/Stops the active loop.
  - **Implementation:** Maps to `scripts/cancel.sh`.

- **`/help-pickle`** (`commands/help-pickle.toml`):
  - **Purpose:** Displays help information for the extension.

### 4. Scripts
Located in `scripts/`, these Bash scripts handle the logic for the extension commands.
- **`setup.sh`**: Initializes the loop state (`state.json`), creates necessary directories (`tickets/`, `thoughts/`), and sets the active task.
- **`cancel.sh`**: Teardown script to stop the loop by setting `active: false` in `state.json`.

### 5. Skills
Located in `skills/`, these provide specialized capabilities for each stage of the engineering lifecycle:

- **`prd-drafter`**: Defines requirements and scope.
- **`ticket-manager`**: Manages the work breakdown structure.
- **`code-researcher`**: Analyze existing codebase and patterns.
- **`research-reviewer`**: Validates research objectivity.
- **`implementation-planner`**: Creates detailed technical plans.
- **`plan-reviewer`**: Validates architectural soundness.
- **`code-implementer`**: Executes the plan with rigorous verification.
- **`ruthless-refactorer`**: Cleans up technical debt and "slop".

## Usage

### Starting the Loop
```bash
/pickle "Refactor the authentication module"
```
Optional arguments:
- `--max-iterations <N>`: Stop after N iterations.
- `--completion-promise "TEXT"`: Only stop when the agent outputs `<promise>TEXT</promise>`.

### Stopping the Loop
```bash
/eat-pickle
```

### 6. Council of Ricks (Multi-Agent Teams)

The Council of Ricks provides multi-agent team orchestration, enabling multiple Gemini CLI agents to work in parallel on complex tasks. Each agent runs in a separate tmux pane for visual monitoring.

#### Architecture

- **`scripts/team_manager.py`**: Core team management — creates teams, spawns agents in tmux panes, monitors progress, handles shutdown.
- **`scripts/agent_mailbox.py`**: Inter-agent communication via file-based mailbox. Supports direct messages and broadcasts.
- **`scripts/task_board.py`**: Shared task management with status tracking and dependencies.
- **`commands/council.toml`**: Entry point command for starting a Council session.
- **`skills/council-rick/SKILL.md`**: Skill definition for the Manager Rick persona.

#### Key Features

1. **Team Creation**: Shared task board + agent mailboxes in `~/.gemini/extensions/pickle-rick/teams/`
2. **Agent Spawning**: Each agent runs `gemini` CLI in a separate tmux pane
3. **Inter-Agent Messaging**: Direct messages (DM) and broadcasts between agents
4. **Shared Task Board**: Create, claim, update, complete tasks with dependency tracking
5. **Manager Oversight**: View agent logs, check inboxes, monitor task progress
6. **Visual Monitoring**: Attach to the tmux session to watch all agents in real-time
7. **Graceful Shutdown**: Message-based shutdown protocol with force-kill fallback

#### Starting a Council Session
```bash
/council "Build a REST API for user management"
```

#### Managing Teams via CLI
```bash
# Create a team
python3 scripts/team_manager.py create --name "my-team" --description "Feature X"

# Spawn agents
python3 scripts/team_manager.py spawn --team "my-team" --name "rick-dev" --type dev --task "Implement the API"
python3 scripts/team_manager.py spawn --team "my-team" --name "rick-tester" --type tester --task "Write integration tests"

# Monitor
python3 scripts/team_manager.py list --team "my-team"
python3 scripts/team_manager.py logs --team "my-team" --agent "rick-dev"

# Attach to tmux session
python3 scripts/team_manager.py attach --team "my-team"

# Shutdown
python3 scripts/team_manager.py shutdown --team "my-team"
python3 scripts/team_manager.py delete --team "my-team"
```
