#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from team_manager import TeamManager


class TestTeamManagerCreate(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.team_dir = os.path.join(self.test_dir, "test-team")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_team(self):
        mgr = TeamManager(team_dir=self.team_dir)
        config = mgr.create_team("Test team description")

        self.assertEqual(config["name"], "test-team")
        self.assertEqual(config["description"], "Test team description")
        self.assertEqual(len(config["members"]), 1)
        self.assertEqual(config["members"][0]["name"], "manager")
        self.assertEqual(config["members"][0]["type"], "manager")

        # Verify directory structure
        self.assertTrue(os.path.exists(os.path.join(self.team_dir, "config.json")))
        self.assertTrue(os.path.exists(os.path.join(self.team_dir, "logs")))
        self.assertTrue(os.path.exists(os.path.join(self.team_dir, "mailbox", "manager", "inbox")))

    def test_create_duplicate_team_raises(self):
        mgr = TeamManager(team_dir=self.team_dir)
        mgr.create_team()

        with self.assertRaises(FileExistsError):
            mgr.create_team()

    def test_load_team(self):
        mgr = TeamManager(team_dir=self.team_dir)
        mgr.create_team("Test")

        mgr2 = TeamManager(team_dir=self.team_dir)
        config = mgr2.load_team()
        self.assertEqual(config["name"], "test-team")

    def test_load_nonexistent_team_raises(self):
        mgr = TeamManager(team_dir=os.path.join(self.test_dir, "nonexistent"))
        with self.assertRaises(FileNotFoundError):
            mgr.load_team()


class TestTeamManagerSpawn(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.team_dir = os.path.join(self.test_dir, "test-team")
        self.mgr = TeamManager(team_dir=self.team_dir)
        self.mgr.create_team("Test")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    def test_spawn_agent_creates_mailbox(self, mock_run):
        # Mock tmux commands
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")

        self.mgr.tmux_session = "test-session"
        member = self.mgr.spawn_agent("rick-dev", "dev", "Implement feature X")

        self.assertEqual(member["name"], "rick-dev")
        self.assertEqual(member["type"], "dev")
        self.assertEqual(member["status"], "active")

        # Verify mailbox was created
        inbox_path = os.path.join(self.team_dir, "mailbox", "rick-dev", "inbox")
        self.assertTrue(os.path.exists(inbox_path))

    @patch("subprocess.run")
    def test_spawn_agent_updates_config(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")

        self.mgr.tmux_session = "test-session"
        self.mgr.spawn_agent("rick-dev", "dev", "Task")

        config = json.loads(Path(self.team_dir, "config.json").read_text())
        self.assertEqual(len(config["members"]), 2)  # manager + rick-dev
        self.assertEqual(config["members"][1]["name"], "rick-dev")

    @patch("subprocess.run")
    def test_spawn_duplicate_agent_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")

        self.mgr.tmux_session = "test-session"
        self.mgr.spawn_agent("rick-dev", "dev", "Task")

        with self.assertRaises(ValueError):
            self.mgr.spawn_agent("rick-dev", "dev", "Another task")

    def test_build_agent_prompt_contains_tools(self):
        prompt = self.mgr._build_agent_prompt("rick-dev", "dev", "Build X", "/ext")

        self.assertIn("rick-dev", prompt)
        self.assertIn("dev", prompt)
        self.assertIn("Build X", prompt)
        self.assertIn("agent_mailbox.py", prompt)
        self.assertIn("task_board.py", prompt)
        self.assertIn("send", prompt)
        self.assertIn("broadcast", prompt)
        self.assertIn("read", prompt)
        self.assertIn("list-agents", prompt)
        self.assertIn("claim", prompt)
        self.assertIn("complete", prompt)


class TestTeamManagerMonitoring(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.team_dir = os.path.join(self.test_dir, "test-team")
        self.mgr = TeamManager(team_dir=self.team_dir)
        self.mgr.create_team("Test")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_list_agents_returns_manager(self):
        agents = self.mgr.list_agents()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["name"], "manager")

    @patch("subprocess.run")
    def test_list_agents_after_spawn(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")
        self.mgr.tmux_session = "test-session"
        self.mgr.spawn_agent("rick-dev", "dev", "Task")

        agents = self.mgr.list_agents()
        self.assertEqual(len(agents), 2)
        names = [a["name"] for a in agents]
        self.assertIn("manager", names)
        self.assertIn("rick-dev", names)

    def test_get_agent_logs_empty(self):
        logs = self.mgr.get_agent_logs("manager")
        self.assertEqual(logs, "")

    def test_get_agent_logs_with_content(self):
        log_path = os.path.join(self.team_dir, "logs", "rick-dev.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            for i in range(100):
                f.write(f"Line {i}\n")

        logs = self.mgr.get_agent_logs("rick-dev", tail=10)
        lines = logs.strip().splitlines()
        self.assertEqual(len(lines), 10)
        self.assertEqual(lines[-1], "Line 99")


class TestTeamManagerShutdown(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.team_dir = os.path.join(self.test_dir, "test-team")
        self.mgr = TeamManager(team_dir=self.team_dir)
        self.mgr.create_team("Test")
        # Create an agent mailbox
        from agent_mailbox import AgentMailbox
        AgentMailbox.create_agent_mailbox(self.team_dir, "rick-dev")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_shutdown_agent_sends_message(self):
        self.mgr.shutdown_agent("rick-dev", "Work done")

        from agent_mailbox import AgentMailbox
        agent_mailbox = AgentMailbox(self.team_dir, "rick-dev")
        msgs = agent_mailbox.read_inbox()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "shutdown_request")
        self.assertEqual(msgs[0]["content"], "Work done")

    def test_shutdown_all_sends_to_all(self):
        from agent_mailbox import AgentMailbox
        AgentMailbox.create_agent_mailbox(self.team_dir, "rick-tester")

        self.mgr.shutdown_all("All done")

        for name in ["rick-dev", "rick-tester"]:
            mb = AgentMailbox(self.team_dir, name)
            msgs = mb.read_inbox()
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["type"], "shutdown_request")

    @patch("subprocess.run")
    def test_delete_team(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(os.path.exists(self.team_dir))
        self.mgr.delete_team()
        self.assertFalse(os.path.exists(self.team_dir))


if __name__ == "__main__":
    unittest.main()
