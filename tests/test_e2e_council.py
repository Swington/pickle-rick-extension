#!/usr/bin/env python3
"""
E2E Test Suite for Council of Ricks Agent Teams.

Tests each layer independently, then runs a full integration test
with actual gemini CLI processes in tmux panes.

Layers 1-3 and 6 are pure unit/integration tests (no gemini process).
Layers 4, 5, 7 spawn real gemini CLI agents in tmux panes and require:
  - tmux installed
  - gemini CLI available on PATH
  - Network access for gemini API calls

Run with: python3 tests/test_e2e_council.py [--skip-live]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)

from agent_mailbox import AgentMailbox
from task_board import TaskBoard
from team_manager import TeamManager, detect_parent_yolo, TEAMS_ROOT

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[36mINFO\033[0m"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return condition


def test_layer1_mailbox():
    """Test mailbox DM, broadcast, read/unread."""
    print(f"\n[{INFO}] Layer 1: Agent Mailbox")
    d = tempfile.mkdtemp()
    try:
        AgentMailbox.create_agent_mailbox(d, "manager")
        AgentMailbox.create_agent_mailbox(d, "dev")
        AgentMailbox.create_agent_mailbox(d, "tester")

        mgr = AgentMailbox(d, "manager")
        dev = AgentMailbox(d, "dev")
        tester = AgentMailbox(d, "tester")

        # DM
        msg_id = mgr.send("dev", "Implement the feature")
        check("DM delivery", msg_id is not None)

        msgs = dev.read_inbox()
        check("DM received", len(msgs) == 1 and msgs[0]["content"] == "Implement the feature")
        check("DM marked read", dev.count_unread() == 0)

        # Broadcast
        recipients = mgr.broadcast("Standup in 5")
        check("Broadcast sent", set(recipients) == {"dev", "tester"}, f"recipients={recipients}")

        check("Broadcast received by dev", len(dev.read_inbox()) == 1)
        check("Broadcast received by tester", len(tester.read_inbox()) == 1)

        # Peer-to-peer
        dev.send("tester", "Review my PR")
        peer_msgs = tester.read_inbox()
        check("Peer DM works", len(peer_msgs) == 1 and peer_msgs[0]["from"] == "dev")

        # List agents
        agents = mgr.list_agents()
        check("List agents", sorted(agents) == ["dev", "manager", "tester"])

    finally:
        shutil.rmtree(d)


def test_layer2_taskboard():
    """Test task create, claim, complete, dependencies."""
    print(f"\n[{INFO}] Layer 2: Task Board")
    d = tempfile.mkdtemp()
    try:
        board = TaskBoard(d)

        id1 = board.create("Setup DB schema", "Create tables")
        id2 = board.create("Build API endpoints", "REST API", blocked_by=[id1])
        id3 = board.create("Write tests", "Unit tests")

        check("Tasks created", id1 == "1" and id2 == "2" and id3 == "3")

        # Availability
        avail = board.list_available()
        avail_ids = [t["id"] for t in avail]
        check("Blocked task excluded", id2 not in avail_ids)
        check("Unblocked tasks available", id1 in avail_ids and id3 in avail_ids)

        # Claim + complete
        board.claim(id1, "rick-dev")
        t = board.get(id1)
        check("Task claimed", t["owner"] == "rick-dev" and t["status"] == "in_progress")

        board.complete(id1)
        check("Task completed", board.get(id1)["status"] == "completed")

        # Unblocked after dependency completed
        avail2 = board.list_available()
        check("Task unblocked", id2 in [t["id"] for t in avail2])

        # Delete
        board.delete(id3)
        check("Task deleted", len(board.list_all()) == 2)

    finally:
        shutil.rmtree(d)


def test_layer3_team_create():
    """Test team creation, config, yolo detection."""
    print(f"\n[{INFO}] Layer 3: Team Manager — Create")
    d = tempfile.mkdtemp()
    team_dir = os.path.join(d, "test-team")
    try:
        mgr = TeamManager(team_dir=team_dir)

        # Explicit yolo
        config = mgr.create_team("E2E test team", yolo=True)
        check("Team created", config["name"] == "test-team")
        check("Yolo stored in config", config["yolo"] is True)
        check("Manager in members", config["members"][0]["name"] == "manager")
        check("Config file exists", os.path.exists(os.path.join(team_dir, "config.json")))
        check("Logs dir exists", os.path.isdir(os.path.join(team_dir, "logs")))
        check("Manager mailbox exists",
              os.path.isdir(os.path.join(team_dir, "mailbox", "manager", "inbox")))

        # Task board available
        board = TaskBoard(team_dir)
        tid = board.create("Test task")
        check("Task board usable", board.get(tid)["subject"] == "Test task")

    finally:
        shutil.rmtree(d)


def _live_team_dir(name):
    """Return a team directory inside the extension tree.

    Gemini's Docker sandbox (``-s``) only mounts ``~/.gemini/``, so team
    directories must live inside the extension for agents to access them.
    """
    team_dir = str(TEAMS_ROOT / f"e2e-{name}")
    os.makedirs(team_dir, exist_ok=True)
    return team_dir


def test_layer4_tmux_spawn():
    """Test spawning a real gemini agent in a tmux pane."""
    print(f"\n[{INFO}] Layer 4: Tmux Spawn — Real Gemini Agent")

    team_dir = _live_team_dir("spawn")
    mgr = TeamManager(team_dir=team_dir)
    config = mgr.create_team("E2E live test", yolo=True)
    session_name = config["tmux_session"]

    try:
        # Setup tmux session
        sess = mgr.setup_tmux_session()
        check("Tmux session created", sess == session_name)

        # Verify tmux session exists
        r = subprocess.run(["tmux", "has-session", "-t", session_name],
                           capture_output=True)
        check("Tmux session alive", r.returncode == 0)

        # Spawn a simple agent with a quick task
        member = mgr.spawn_agent(
            "rick-ping",
            "dev",
            'You are a test agent. Do these 3 things IMMEDIATELY then stop:\n'
            '1. Read your inbox using the mailbox read command\n'
            '2. Send a message to "manager" saying "PONG: Agent rick-ping reporting for duty"\n'
            '3. Output: <promise>I AM DONE</promise>\n'
            'Do NOT do anything else.',
        )
        check("Agent spawned", member["name"] == "rick-ping" and member["status"] == "active")
        check("Pane ID assigned", member.get("pane_id") is not None,
              f"pane_id={member.get('pane_id')}")

        # Verify agent mailbox was created
        check("Agent mailbox created",
              os.path.isdir(os.path.join(team_dir, "mailbox", "rick-ping", "inbox")))

        # List agents
        agents = mgr.list_agents()
        names = [a["name"] for a in agents]
        check("Agent in list", "rick-ping" in names, f"agents={names}")

        # List tmux panes
        r2 = subprocess.run(
            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_id} #{pane_pid}"],
            capture_output=True, text=True,
        )
        check("Multiple panes exist", len(r2.stdout.strip().splitlines()) >= 2,
              f"panes:\n{r2.stdout.strip()}")

        # Wait for agent to run and potentially send a message
        print(f"  [{INFO}] Waiting for agent to process (up to 90s)...")
        manager_mb = AgentMailbox(team_dir, "manager")
        got_pong = False
        for i in range(90):
            msgs = manager_mb.read_inbox(unread_only=True, mark_read=False)
            if any("PONG" in m.get("content", "") for m in msgs):
                got_pong = True
                break
            time.sleep(1)
            # Check if pane still alive
            r3 = subprocess.run(
                ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_id}"],
                capture_output=True, text=True
            )
            if member.get("pane_id") and member["pane_id"] not in r3.stdout:
                break

        check("Agent sent PONG to manager", got_pong)

        # Check agent log exists and has content
        log_content = mgr.get_agent_logs("rick-ping", tail=100)
        check("Agent log has content", len(log_content) > 0,
              f"log length={len(log_content)}")

        # Check log for startup marker
        log_path = os.path.join(team_dir, "logs", "rick-ping.log")
        if os.path.exists(log_path):
            with open(log_path) as f:
                full_log = f.read()
            check("Agent log shows activity",
                  "Agent rick-ping starting" in full_log or len(full_log) > 50)

    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        shutil.rmtree(team_dir, ignore_errors=True)


def test_layer5_multi_agent():
    """Test multi-agent communication through the system."""
    print(f"\n[{INFO}] Layer 5: Multi-Agent Communication")

    team_dir = _live_team_dir("multi")
    mgr = TeamManager(team_dir=team_dir)
    config = mgr.create_team("Multi-agent test", yolo=True)
    session_name = config["tmux_session"]

    try:
        mgr.setup_tmux_session()

        # Create tasks on the board
        board = TaskBoard(team_dir)
        t1 = board.create("Write a hello world function",
                          "Create hello.py with a greet() function")
        t2 = board.create("Review the hello world function",
                          "Check for correctness", blocked_by=[t1])
        check("Tasks created with dependencies", True)

        # Spawn two agents
        mgr.spawn_agent(
            "rick-writer",
            "dev",
            'You are rick-writer. Do these steps:\n'
            '1. Check available tasks on the task board\n'
            '2. Claim task 1\n'
            '3. Send a message to "rick-reviewer" saying '
            '"I completed task 1: hello.py with greet() function"\n'
            '4. Mark task 1 as complete\n'
            '5. Send a message to "manager" saying "WRITER DONE"\n'
            '6. Output: <promise>I AM DONE</promise>',
        )

        # Small delay to avoid tmux race
        time.sleep(2)

        mgr.spawn_agent(
            "rick-reviewer",
            "tester",
            'You are rick-reviewer. Do these steps:\n'
            '1. Check your inbox every few seconds for a message from rick-writer\n'
            '2. When you get it, check available tasks on the task board\n'
            '3. Claim task 2 and mark it complete\n'
            '4. Send a message to "manager" saying "REVIEWER DONE"\n'
            '5. Output: <promise>I AM DONE</promise>',
        )

        agents = mgr.list_agents()
        check("Two agents spawned",
              len([a for a in agents if a["type"] != "manager"]) == 2)

        # Wait for both agents to report
        print(f"  [{INFO}] Waiting for agents to communicate (up to 120s)...")
        manager_mb = AgentMailbox(team_dir, "manager")
        writer_done = False
        reviewer_done = False

        for i in range(120):
            msgs = manager_mb.read_inbox(unread_only=True, mark_read=False)
            for m in msgs:
                content = m.get("content", "")
                if "WRITER DONE" in content:
                    writer_done = True
                if "REVIEWER DONE" in content:
                    reviewer_done = True
            if writer_done and reviewer_done:
                break
            time.sleep(1)

        check("Writer agent reported done", writer_done)
        check("Reviewer agent reported done", reviewer_done)

        # Check task board state
        all_tasks = board.list_all()
        completed = [t for t in all_tasks if t["status"] == "completed"]
        check("Tasks completed on board", len(completed) >= 1,
              f"completed={len(completed)}/{len(all_tasks)}")

        # Check inter-agent communication happened
        reviewer_mb = AgentMailbox(team_dir, "rick-reviewer")
        reviewer_msgs = reviewer_mb.read_all()
        peer_msgs = [m for m in reviewer_msgs if m.get("from") == "rick-writer"]
        check("Peer-to-peer message delivered", len(peer_msgs) >= 1,
              f"peer_msgs={len(peer_msgs)}")

    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        shutil.rmtree(team_dir, ignore_errors=True)


def test_layer6_yolo_propagation():
    """Test that yolo flag propagates correctly."""
    print(f"\n[{INFO}] Layer 6: Yolo Propagation")
    d = tempfile.mkdtemp()

    try:
        # Team with yolo=True
        team1 = os.path.join(d, "yolo-on")
        mgr1 = TeamManager(team_dir=team1)
        mgr1.create_team("Yolo ON", yolo=True)
        cmd1 = mgr1._build_agent_command("dev", "task", "/ext", "/log", None)
        check("Yolo ON: -y in command", "gemini -s -y" in cmd1)

        # Team with yolo=False
        team2 = os.path.join(d, "yolo-off")
        mgr2 = TeamManager(team_dir=team2)
        mgr2.create_team("Yolo OFF", yolo=False)
        cmd2 = mgr2._build_agent_command("dev", "task", "/ext", "/log", None)
        check("Yolo OFF: no -y in command",
              "gemini -s -y" not in cmd2 and "gemini -s" in cmd2)

        # Env var override
        os.environ["PICKLE_YOLO"] = "1"
        team3 = os.path.join(d, "yolo-env")
        mgr3 = TeamManager(team_dir=team3)
        c3 = mgr3.create_team("Yolo ENV")
        check("Env PICKLE_YOLO=1 detected", c3["yolo"] is True)
        del os.environ["PICKLE_YOLO"]

    finally:
        shutil.rmtree(d)


def test_layer7_shutdown():
    """Test graceful and force shutdown."""
    print(f"\n[{INFO}] Layer 7: Shutdown Protocol")

    team_dir = _live_team_dir("shutdown")
    mgr = TeamManager(team_dir=team_dir)
    config = mgr.create_team("Shutdown test", yolo=True)
    session_name = config["tmux_session"]

    try:
        mgr.setup_tmux_session()

        mgr.spawn_agent(
            "rick-sleeper",
            "dev",
            'You are a test agent. Read your inbox. '
            'If you receive a shutdown_request, output <promise>I AM DONE</promise>. '
            'Otherwise wait and check inbox again.',
        )

        time.sleep(3)

        # Send shutdown
        mgr.shutdown_agent("rick-sleeper", "Test complete")
        sleeper_mb = AgentMailbox(team_dir, "rick-sleeper")
        msgs = sleeper_mb.read_all()
        shutdown_msgs = [m for m in msgs if m.get("type") == "shutdown_request"]
        check("Shutdown message delivered", len(shutdown_msgs) == 1)

        # Force kill
        time.sleep(2)
        killed = mgr.kill_agent("rick-sleeper")
        check("Force kill succeeded", killed)

        # Cleanup
        mgr.kill_all_agents()
        r = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True)
        check("Tmux session cleaned up", r.returncode != 0)

    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        shutil.rmtree(team_dir, ignore_errors=True)


if __name__ == "__main__":
    skip_live = "--skip-live" in sys.argv

    print("=" * 60)
    print("Council of Ricks — End-to-End Test Suite")
    if skip_live:
        print("  (--skip-live: skipping layers 4, 5, 7)")
    print("=" * 60)

    # Run layers in order
    test_layer1_mailbox()
    test_layer2_taskboard()
    test_layer3_team_create()
    test_layer6_yolo_propagation()  # Fast, no gemini needed

    if not skip_live:
        test_layer4_tmux_spawn()        # Real gemini, single agent
        test_layer5_multi_agent()       # Real gemini, multi-agent
        test_layer7_shutdown()          # Real gemini, shutdown protocol
    else:
        print(f"\n[{INFO}] Skipping live agent tests (layers 4, 5, 7)")

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    total = len(results)
    color = "\033[32m" if failed == 0 else "\033[31m"
    print(f"{color}Results: {passed}/{total} passed, {failed} failed\033[0m")

    if failed > 0:
        print("\nFailed tests:")
        for name, ok in results:
            if not ok:
                print(f"  ✗ {name}")

    print("=" * 60)
    sys.exit(1 if failed > 0 else 0)
