#!/usr/bin/env python3
"""
Team Manager: Multi-agent team orchestration for Pickle Rick.

Creates and manages teams of Gemini CLI agents running in tmux panes.
Replicates Claude Code agent teams functionality:
- Team creation with shared task board
- Agent spawning in separate tmux panes
- Inter-agent messaging (DM + broadcast)
- Manager oversight and monitoring
- Graceful shutdown protocol
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import pickle_utils as utils
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import pickle_utils as utils

from agent_mailbox import AgentMailbox
from task_board import TaskBoard

TEAMS_ROOT = Path.home() / ".gemini" / "extensions" / "pickle-rick" / "teams"


def detect_current_tmux_session():
    """Return the current tmux session name if running inside tmux.

    Checks $TMUX env var first, then falls back to querying tmux directly.
    Returns None if not inside a tmux session.
    """
    tmux_env = os.environ.get("TMUX", "")
    if tmux_env:
        # $TMUX format: /tmp/tmux-UID/default,PID,INDEX
        # Get session name from tmux
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{session_name}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, FileNotFoundError):
            pass
    return None


def detect_parent_yolo():
    """Detect if the parent gemini process was launched with --yolo or -y.

    Checks (in order):
    1. PICKLE_YOLO env var (explicit override)
    2. /proc/<ppid>/cmdline on Linux for --yolo, -y, or --approval-mode yolo
    3. Falls back to False if undetectable
    """
    # 1. Explicit env var override
    env_val = os.environ.get("PICKLE_YOLO", "").lower()
    if env_val in ("1", "true", "yes"):
        return True
    if env_val in ("0", "false", "no"):
        return False

    # 2. Inspect parent process cmdline (Linux)
    try:
        ppid = os.getppid()
        cmdline_path = Path(f"/proc/{ppid}/cmdline")
        if cmdline_path.exists():
            raw = cmdline_path.read_bytes()
            args = raw.decode("utf-8", errors="replace").split("\0")
            for i, arg in enumerate(args):
                if arg in ("--yolo", "-y"):
                    return True
                if arg == "--approval-mode" and i + 1 < len(args) and args[i + 1] == "yolo":
                    return True
    except (OSError, PermissionError):
        pass

    return False


class TeamManager:
    """Manages a team of Gemini CLI agents in tmux panes."""

    def __init__(self, team_name=None, team_dir=None):
        if team_dir:
            self.team_dir = Path(team_dir)
            self.team_name = self.team_dir.name
        else:
            self.team_name = team_name
            self.team_dir = TEAMS_ROOT / team_name
        self.config_path = self.team_dir / "config.json"
        self.board = TaskBoard(str(self.team_dir))
        self.tmux_session = None

    # ── Team Lifecycle ───────────────────────────────────────────────

    def create_team(self, description="", yolo=None):
        """Create a new team with directory structure.

        Args:
            description: Human-readable team purpose.
            yolo: Propagate --yolo flag to subagents. If None, auto-detects
                  from the parent gemini process.
        """
        if self.config_path.exists():
            raise FileExistsError(f"Team '{self.team_name}' already exists")

        self.team_dir.mkdir(parents=True, exist_ok=True)
        (self.team_dir / "logs").mkdir(exist_ok=True)

        # Auto-detect yolo mode from parent process if not explicitly set
        if yolo is None:
            yolo = detect_parent_yolo()

        # Create manager mailbox
        AgentMailbox.create_agent_mailbox(str(self.team_dir), "manager")

        # Prefer opening panes in the current tmux session if we're already
        # inside one; otherwise create a dedicated session later.
        current_session = detect_current_tmux_session()
        tmux_session = current_session or f"pickle-team-{self.team_name}"

        # Record the manager's pane so agent panes split from it, not
        # whatever window the user happens to be looking at.
        manager_pane = None
        if current_session:
            try:
                r = subprocess.run(
                    ["tmux", "display-message", "-p", "#{pane_id}"],
                    capture_output=True, text=True,
                )
                if r.returncode == 0 and r.stdout.strip():
                    manager_pane = r.stdout.strip()
            except (OSError, FileNotFoundError):
                pass

        # Label the manager's pane
        if manager_pane:
            subprocess.run(
                ["tmux", "select-pane", "-t", manager_pane,
                 "-T", f"manager ({self.team_name})"],
                capture_output=True,
            )

        config = {
            "name": self.team_name,
            "description": description,
            "yolo": yolo,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tmux_session": tmux_session,
            "use_existing_session": current_session is not None,
            "manager_pane": manager_pane,
            "members": [
                {
                    "name": "manager",
                    "type": "manager",
                    "status": "active",
                    "pane_id": manager_pane,
                    "pid": os.getpid(),
                }
            ],
        }
        self.config_path.write_text(json.dumps(config, indent=2))
        self.tmux_session = config["tmux_session"]
        return config

    def load_team(self):
        """Load existing team configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Team '{self.team_name}' not found")
        config = json.loads(self.config_path.read_text())
        self.tmux_session = config.get("tmux_session")
        return config

    def delete_team(self):
        """Delete the team and all its resources."""
        if self.team_dir.exists():
            config = json.loads(self.config_path.read_text()) if self.config_path.exists() else {}
            use_existing = config.get("use_existing_session", False)

            if not use_existing:
                # Only kill the tmux session if we created it ourselves
                session = config.get("tmux_session", f"pickle-team-{self.team_name}")
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )
            else:
                # Kill individual agent panes but leave the session alive
                for member in config.get("members", []):
                    pane_id = member.get("pane_id")
                    if pane_id:
                        subprocess.run(
                            ["tmux", "kill-pane", "-t", pane_id],
                            capture_output=True,
                        )
            shutil.rmtree(self.team_dir)

    # ── Agent Spawning ───────────────────────────────────────────────

    def setup_tmux_session(self):
        """Ensure a tmux session is ready for agent panes.

        If the team was created inside an existing tmux session, that session
        is reused and agent panes open right next to the user's terminal.
        Otherwise a dedicated detached session is created.
        """
        config = self.load_team()
        session = config["tmux_session"]
        use_existing = config.get("use_existing_session", False)

        # Check if session already exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True,
        )
        if result.returncode == 0:
            self.tmux_session = session
            return session

        if use_existing:
            # The saved session disappeared — fall back to a new one
            session = f"pickle-team-{self.team_name}"
            config["tmux_session"] = session
            config["use_existing_session"] = False
            self.config_path.write_text(json.dumps(config, indent=2))

        # Create new tmux session (detached)
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-n", "manager"],
            check=True,
        )
        # Set status bar
        subprocess.run(
            ["tmux", "set-option", "-t", session, "status-left",
             f"[Team: {self.team_name}] "],
            capture_output=True,
        )
        self.tmux_session = session
        return session

    def spawn_agent(self, agent_name, agent_type, task_prompt, cwd=None):
        """Spawn a new agent in a tmux pane.

        Args:
            agent_name: Unique name for the agent
            agent_type: Role type (dev, architect, tester, auditor, researcher)
            task_prompt: The task for the agent to work on
            cwd: Working directory for the agent
        Returns:
            dict with agent info including pane_id
        """
        config = self.load_team()

        # Check for duplicate names
        for member in config["members"]:
            if member["name"] == agent_name:
                raise ValueError(f"Agent '{agent_name}' already exists in team")

        # Create agent mailbox
        AgentMailbox.create_agent_mailbox(str(self.team_dir), agent_name)

        # Ensure tmux session exists
        if not self.tmux_session:
            self.setup_tmux_session()

        # Build the agent wrapper command
        extension_root = str(Path.home() / ".gemini" / "extensions" / "pickle-rick")
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = str(self.team_dir / "logs" / f"{agent_name}.log")

        # Build agent boot prompt with communication tools
        agent_prompt = self._build_agent_prompt(
            agent_name, agent_type, task_prompt, extension_root
        )

        # Build gemini command
        cmd_parts = [
            "bash", "-c",
            self._build_agent_command(
                agent_name, agent_prompt, extension_root, log_file, cwd
            ),
        ]

        # Split from the manager's pane so agents always appear next to the
        # gemini instance that spawned them, not in the user's active window.
        split_target = config.get("manager_pane") or self.tmux_session

        # Create new tmux pane by splitting
        result = subprocess.run(
            ["tmux", "split-window", "-t", split_target, "-h",
             "-P", "-F", "#{pane_id}"] + cmd_parts,
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            # Try vertical split if horizontal fails
            result = subprocess.run(
                ["tmux", "split-window", "-t", split_target, "-v",
                 "-P", "-F", "#{pane_id}"] + cmd_parts,
                capture_output=True, text=True,
            )

        pane_id = result.stdout.strip() if result.returncode == 0 else None

        # Name the pane so the user can identify which agent is which
        if pane_id:
            subprocess.run(
                ["tmux", "select-pane", "-t", pane_id,
                 "-T", f"{agent_name} ({agent_type})"],
                capture_output=True,
            )
            # Enable pane border labels (idempotent)
            subprocess.run(
                ["tmux", "set-option", "-t", self.tmux_session,
                 "pane-border-status", "top"],
                capture_output=True,
            )
            subprocess.run(
                ["tmux", "set-option", "-t", self.tmux_session,
                 "pane-border-format",
                 " #{pane_index}: #{pane_title} "],
                capture_output=True,
            )

        # Rebalance panes in the manager's window
        subprocess.run(
            ["tmux", "select-layout", "-t", split_target, "tiled"],
            capture_output=True,
        )

        # Update config
        member = {
            "name": agent_name,
            "type": agent_type,
            "status": "active",
            "pane_id": pane_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        config["members"].append(member)
        self.config_path.write_text(json.dumps(config, indent=2))

        return member

    def _build_agent_prompt(self, agent_name, agent_type, task_prompt, extension_root):
        """Build the system prompt for an agent with communication tools."""
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        team_dir = str(self.team_dir)

        return f"""# AGENT IDENTITY
You are **{agent_name}** (role: {agent_type}) on team **{self.team_name}**.
You are part of a multi-agent team managed by a Manager Rick.

# YOUR TASK
{task_prompt}

# COMMUNICATION TOOLS
You can communicate with other agents and manage tasks using these commands:

## Send a message to another agent:
```bash
python3 {scripts_dir}/agent_mailbox.py --team-dir "{team_dir}" --agent "{agent_name}" send --to "<recipient>" --content "<message>"
```

## Broadcast a message to all agents:
```bash
python3 {scripts_dir}/agent_mailbox.py --team-dir "{team_dir}" --agent "{agent_name}" broadcast --content "<message>"
```

## Read your inbox (new messages):
```bash
python3 {scripts_dir}/agent_mailbox.py --team-dir "{team_dir}" --agent "{agent_name}" read
```

## List all agents on the team:
```bash
python3 {scripts_dir}/agent_mailbox.py --team-dir "{team_dir}" --agent "{agent_name}" list-agents
```

## List available tasks:
```bash
python3 {scripts_dir}/task_board.py --team-dir "{team_dir}" list --available
```

## List all tasks:
```bash
python3 {scripts_dir}/task_board.py --team-dir "{team_dir}" list
```

## Claim a task:
```bash
python3 {scripts_dir}/task_board.py --team-dir "{team_dir}" claim --id <task_id> --owner "{agent_name}"
```

## Mark task complete:
```bash
python3 {scripts_dir}/task_board.py --team-dir "{team_dir}" complete --id <task_id>
```

## Create a new task:
```bash
python3 {scripts_dir}/task_board.py --team-dir "{team_dir}" create --subject "<title>" --description "<details>"
```

# PROTOCOL
1. Check your inbox regularly for messages from the manager or peers.
2. When you finish your task, send a message to "manager" with your results.
3. Evaluate peers' work when asked - be thorough and unforgiving.
4. When you receive a shutdown message, output: <promise>I AM DONE</promise>

# STANDARDS
- Follow TDD. Write tests first.
- No slop. No boilerplate. No lazy typing.
- Be precise in your communication. Include code in messages when suggesting fixes.
"""

    @staticmethod
    def _resolve_gemini_model():
        """Read the model from ~/.gemini/settings.json.

        The settings file stores the model as either a plain string or a
        nested object ``{"model": "<id>"}``.  The gemini CLI's ``-s`` mode
        sometimes fails to parse the nested form, so we resolve it here and
        pass ``--model`` explicitly.

        Returns the model id string, or None if unresolvable.
        """
        settings_path = Path.home() / ".gemini" / "settings.json"
        try:
            if settings_path.exists():
                data = json.loads(settings_path.read_text())
                model = data.get("model")
                if isinstance(model, dict):
                    return model.get("model")
                if isinstance(model, str):
                    return model
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def _build_agent_command(self, agent_name, prompt, extension_root, log_file, cwd):
        """Build the shell command to run the agent.

        Reads the team config to determine whether to propagate --yolo.
        Resolves the gemini model from settings to avoid the
        ``model.startsWith is not a function`` error.
        """
        import shlex

        config = self.load_team()
        yolo = config.get("yolo", False)

        cwd_str = cwd or os.getcwd()
        includes = [extension_root, os.path.join(extension_root, "skills")]

        cmd = f'echo "=== Agent {agent_name} starting ===" && '
        cmd += "gemini"
        if yolo:
            cmd += " -y"

        # Resolve model to avoid nested-object parse failure
        model = self._resolve_gemini_model()
        if model:
            cmd += f" --model {shlex.quote(model)}"

        for inc in includes:
            cmd += f" --include-directories {shlex.quote(inc)}"
        cmd += f" -p {shlex.quote(prompt)}"
        cmd += f" 2>&1 | tee {shlex.quote(log_file)}"
        cmd += f"; echo '=== Agent {agent_name} exited ==='"

        return cmd

    # ── Monitoring ───────────────────────────────────────────────────

    def list_agents(self):
        """List all agents and their status."""
        config = self.load_team()
        agents = []
        for member in config["members"]:
            info = {
                "name": member["name"],
                "type": member["type"],
                "status": member["status"],
                "pane_id": member.get("pane_id"),
            }
            # Check if tmux pane is still alive
            if member.get("pane_id") and self.tmux_session:
                result = subprocess.run(
                    ["tmux", "list-panes", "-t", self.tmux_session,
                     "-F", "#{pane_id} #{pane_pid}"],
                    capture_output=True, text=True,
                )
                pane_alive = member["pane_id"] in result.stdout
                info["alive"] = pane_alive
                if not pane_alive and member["status"] == "active":
                    info["status"] = "exited"
            agents.append(info)
        return agents

    def get_agent_logs(self, agent_name, tail=50):
        """Get the last N lines of an agent's log."""
        log_path = self.team_dir / "logs" / f"{agent_name}.log"
        if not log_path.exists():
            return ""
        lines = log_path.read_text().splitlines()
        return "\n".join(lines[-tail:])

    def check_agent_inbox(self, agent_name):
        """Check an agent's inbox (manager oversight)."""
        mailbox = AgentMailbox(str(self.team_dir), agent_name)
        return mailbox.read_all()

    # ── Shutdown ─────────────────────────────────────────────────────

    def shutdown_agent(self, agent_name, reason="Task complete"):
        """Send shutdown request to an agent."""
        mailbox = AgentMailbox(str(self.team_dir), "manager")
        return mailbox.send(agent_name, reason, msg_type="shutdown_request")

    def shutdown_all(self, reason="All tasks complete"):
        """Send shutdown to all agents."""
        mailbox = AgentMailbox(str(self.team_dir), "manager")
        return mailbox.broadcast(reason, msg_type="shutdown_request")

    def kill_agent(self, agent_name):
        """Force kill an agent's tmux pane."""
        config = self.load_team()
        for member in config["members"]:
            if member["name"] == agent_name and member.get("pane_id"):
                subprocess.run(
                    ["tmux", "kill-pane", "-t", member["pane_id"]],
                    capture_output=True,
                )
                member["status"] = "killed"
                self.config_path.write_text(json.dumps(config, indent=2))
                return True
        return False

    def kill_all_agents(self):
        """Force kill all agent panes.

        If the team uses the user's existing tmux session, only the agent
        panes are killed (not the session itself).
        """
        config = self.load_team()
        use_existing = config.get("use_existing_session", False)
        session = config.get("tmux_session")

        if use_existing:
            # Kill individual agent panes, preserve the user's session
            for member in config["members"]:
                pane_id = member.get("pane_id")
                if pane_id:
                    subprocess.run(
                        ["tmux", "kill-pane", "-t", pane_id],
                        capture_output=True,
                    )
        elif session:
            subprocess.run(
                ["tmux", "kill-session", "-t", session],
                capture_output=True,
            )
        for member in config["members"]:
            member["status"] = "killed"
        self.config_path.write_text(json.dumps(config, indent=2))

    # ── Utility ──────────────────────────────────────────────────────

    def attach(self):
        """Attach to the team's tmux session."""
        config = self.load_team()
        session = config.get("tmux_session")
        if session:
            os.execlp("tmux", "tmux", "attach-session", "-t", session)

    @staticmethod
    def list_teams():
        """List all existing teams."""
        teams = []
        if TEAMS_ROOT.exists():
            for team_dir in TEAMS_ROOT.iterdir():
                config_path = team_dir / "config.json"
                if config_path.exists():
                    config = json.loads(config_path.read_text())
                    teams.append({
                        "name": config["name"],
                        "description": config.get("description", ""),
                        "members": len(config.get("members", [])),
                        "created_at": config.get("created_at", ""),
                    })
        return teams


def main():
    """CLI interface for team management."""
    import argparse

    parser = argparse.ArgumentParser(description="Pickle Rick Team Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create team
    create_p = subparsers.add_parser("create", help="Create a team")
    create_p.add_argument("--name", required=True, help="Team name")
    create_p.add_argument("--description", default="", help="Team description")
    yolo_group = create_p.add_mutually_exclusive_group()
    yolo_group.add_argument(
        "--yolo", action="store_true", default=None,
        help="Propagate --yolo (auto-approve) to subagents",
    )
    yolo_group.add_argument(
        "--no-yolo", action="store_true", default=None,
        help="Explicitly disable --yolo for subagents",
    )

    # Spawn agent
    spawn_p = subparsers.add_parser("spawn", help="Spawn an agent")
    spawn_p.add_argument("--team", required=True, help="Team name")
    spawn_p.add_argument("--name", required=True, help="Agent name")
    spawn_p.add_argument("--type", required=True, help="Agent type/role")
    spawn_p.add_argument("--task", required=True, help="Task prompt")
    spawn_p.add_argument("--cwd", default=None, help="Working directory")

    # List agents
    list_p = subparsers.add_parser("list", help="List agents")
    list_p.add_argument("--team", required=True, help="Team name")

    # Agent logs
    logs_p = subparsers.add_parser("logs", help="Get agent logs")
    logs_p.add_argument("--team", required=True, help="Team name")
    logs_p.add_argument("--agent", required=True, help="Agent name")
    logs_p.add_argument("--tail", type=int, default=50, help="Number of lines")

    # Shutdown
    shutdown_p = subparsers.add_parser("shutdown", help="Shutdown agent(s)")
    shutdown_p.add_argument("--team", required=True, help="Team name")
    shutdown_p.add_argument("--agent", default=None, help="Agent name (all if omitted)")

    # Kill
    kill_p = subparsers.add_parser("kill", help="Force kill agent(s)")
    kill_p.add_argument("--team", required=True, help="Team name")
    kill_p.add_argument("--agent", default=None, help="Agent name (all if omitted)")

    # Delete team
    delete_p = subparsers.add_parser("delete", help="Delete a team")
    delete_p.add_argument("--team", required=True, help="Team name")

    # List teams
    subparsers.add_parser("teams", help="List all teams")

    # Attach
    attach_p = subparsers.add_parser("attach", help="Attach to team tmux")
    attach_p.add_argument("--team", required=True, help="Team name")

    args = parser.parse_args()

    if args.command == "create":
        mgr = TeamManager(args.name)
        # Resolve yolo: explicit flag > auto-detect
        yolo = None  # auto-detect
        if getattr(args, "yolo", None):
            yolo = True
        elif getattr(args, "no_yolo", None):
            yolo = False
        config = mgr.create_team(args.description, yolo=yolo)
        print(json.dumps(config, indent=2))

    elif args.command == "spawn":
        mgr = TeamManager(args.team)
        member = mgr.spawn_agent(args.name, args.type, args.task, args.cwd)
        print(json.dumps(member, indent=2))

    elif args.command == "list":
        mgr = TeamManager(args.team)
        agents = mgr.list_agents()
        print(json.dumps(agents, indent=2))

    elif args.command == "logs":
        mgr = TeamManager(args.team)
        print(mgr.get_agent_logs(args.agent, args.tail))

    elif args.command == "shutdown":
        mgr = TeamManager(args.team)
        if args.agent:
            mgr.shutdown_agent(args.agent)
            print(f"Shutdown request sent to {args.agent}")
        else:
            mgr.shutdown_all()
            print("Shutdown request sent to all agents")

    elif args.command == "kill":
        mgr = TeamManager(args.team)
        if args.agent:
            mgr.kill_agent(args.agent)
            print(f"Killed {args.agent}")
        else:
            mgr.kill_all_agents()
            print("Killed all agents")

    elif args.command == "delete":
        mgr = TeamManager(args.team)
        mgr.delete_team()
        print(f"Team '{args.team}' deleted")

    elif args.command == "teams":
        teams = TeamManager.list_teams()
        print(json.dumps(teams, indent=2))

    elif args.command == "attach":
        mgr = TeamManager(args.team)
        mgr.attach()


if __name__ == "__main__":
    main()
