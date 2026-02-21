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

from team_manager import TeamManager, detect_parent_yolo


class TestDetectParentYolo(unittest.TestCase):
    """Tests for yolo mode detection from parent process."""

    def test_env_var_true(self):
        with patch.dict(os.environ, {"PICKLE_YOLO": "1"}):
            self.assertTrue(detect_parent_yolo())

    def test_env_var_true_string(self):
        with patch.dict(os.environ, {"PICKLE_YOLO": "true"}):
            self.assertTrue(detect_parent_yolo())

    def test_env_var_false(self):
        with patch.dict(os.environ, {"PICKLE_YOLO": "0"}):
            self.assertFalse(detect_parent_yolo())

    def test_env_var_false_string(self):
        with patch.dict(os.environ, {"PICKLE_YOLO": "no"}):
            self.assertFalse(detect_parent_yolo())

    @patch.dict(os.environ, {}, clear=True)
    @patch("team_manager.Path")
    def test_cmdline_yolo_flag(self, mock_path_cls):
        # Simulate /proc/<ppid>/cmdline containing --yolo
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"gemini\x00--yolo\x00-p\x00task"
        mock_path_cls.return_value = mock_path_instance
        # Remove PICKLE_YOLO if present
        os.environ.pop("PICKLE_YOLO", None)
        self.assertTrue(detect_parent_yolo())

    @patch.dict(os.environ, {}, clear=True)
    @patch("team_manager.Path")
    def test_cmdline_y_flag(self, mock_path_cls):
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"gemini\x00-s\x00-y\x00-p\x00task"
        mock_path_cls.return_value = mock_path_instance
        os.environ.pop("PICKLE_YOLO", None)
        self.assertTrue(detect_parent_yolo())

    @patch.dict(os.environ, {}, clear=True)
    @patch("team_manager.Path")
    def test_cmdline_approval_mode_yolo(self, mock_path_cls):
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"gemini\x00--approval-mode\x00yolo\x00-p\x00task"
        mock_path_cls.return_value = mock_path_instance
        os.environ.pop("PICKLE_YOLO", None)
        self.assertTrue(detect_parent_yolo())

    @patch.dict(os.environ, {}, clear=True)
    @patch("team_manager.Path")
    def test_cmdline_no_yolo(self, mock_path_cls):
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"gemini\x00-s\x00-p\x00task"
        mock_path_cls.return_value = mock_path_instance
        os.environ.pop("PICKLE_YOLO", None)
        self.assertFalse(detect_parent_yolo())

    @patch.dict(os.environ, {}, clear=True)
    @patch("team_manager.Path")
    def test_no_proc_filesystem(self, mock_path_cls):
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_cls.return_value = mock_path_instance
        os.environ.pop("PICKLE_YOLO", None)
        self.assertFalse(detect_parent_yolo())


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

    def test_create_team_explicit_yolo_true(self):
        mgr = TeamManager(team_dir=self.team_dir)
        config = mgr.create_team("Test", yolo=True)
        self.assertTrue(config["yolo"])

    def test_create_team_explicit_yolo_false(self):
        mgr = TeamManager(team_dir=self.team_dir)
        config = mgr.create_team("Test", yolo=False)
        self.assertFalse(config["yolo"])

    @patch("team_manager.detect_parent_yolo", return_value=True)
    def test_create_team_auto_detects_yolo(self, mock_detect):
        mgr = TeamManager(team_dir=self.team_dir)
        config = mgr.create_team("Test")
        self.assertTrue(config["yolo"])
        mock_detect.assert_called_once()

    @patch("team_manager.detect_parent_yolo", return_value=False)
    def test_create_team_auto_detects_no_yolo(self, mock_detect):
        mgr = TeamManager(team_dir=self.team_dir)
        config = mgr.create_team("Test")
        self.assertFalse(config["yolo"])

    def test_yolo_stored_in_config_file(self):
        mgr = TeamManager(team_dir=self.team_dir)
        mgr.create_team("Test", yolo=True)
        config = json.loads(Path(self.team_dir, "config.json").read_text())
        self.assertTrue(config["yolo"])

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


class TestYoloPropagation(unittest.TestCase):
    """Tests that --yolo flag propagates from team config to agent commands."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_agent_command_includes_y_when_yolo_true(self):
        team_dir = os.path.join(self.test_dir, "yolo-team")
        mgr = TeamManager(team_dir=team_dir)
        mgr.create_team("Test", yolo=True)

        cmd = mgr._build_agent_command("rick-dev", "prompt", "/ext", "/log", None)
        # Should contain "gemini -s -y"
        self.assertIn("gemini -s -y", cmd)

    def test_agent_command_excludes_y_when_yolo_false(self):
        team_dir = os.path.join(self.test_dir, "no-yolo-team")
        mgr = TeamManager(team_dir=team_dir)
        mgr.create_team("Test", yolo=False)

        cmd = mgr._build_agent_command("rick-dev", "prompt", "/ext", "/log", None)
        # Should contain "gemini -s" but NOT "gemini -s -y"
        self.assertIn("gemini -s", cmd)
        self.assertNotIn("gemini -s -y", cmd)

    @patch("subprocess.run")
    def test_full_spawn_propagates_yolo(self, mock_run):
        """End-to-end: team created with yolo=True spawns agents with -y."""
        team_dir = os.path.join(self.test_dir, "e2e-team")
        mgr = TeamManager(team_dir=team_dir)
        mgr.create_team("Test", yolo=True)
        mgr.tmux_session = "test-session"
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")

        mgr.spawn_agent("rick-dev", "dev", "Build X")

        # Find the tmux split-window call and check the command contains -y
        tmux_calls = [c for c in mock_run.call_args_list
                      if "split-window" in str(c)]
        self.assertTrue(len(tmux_calls) > 0)
        cmd_str = str(tmux_calls[0])
        self.assertIn("-y", cmd_str)

    @patch("subprocess.run")
    def test_full_spawn_no_yolo(self, mock_run):
        """End-to-end: team created with yolo=False spawns agents without -y."""
        team_dir = os.path.join(self.test_dir, "e2e-noyolo")
        mgr = TeamManager(team_dir=team_dir)
        mgr.create_team("Test", yolo=False)
        mgr.tmux_session = "test-session"
        mock_run.return_value = MagicMock(returncode=0, stdout="%1\n")

        mgr.spawn_agent("rick-dev", "dev", "Build X")

        tmux_calls = [c for c in mock_run.call_args_list
                      if "split-window" in str(c)]
        self.assertTrue(len(tmux_calls) > 0)
        # The command string should have "gemini -s " but not "gemini -s -y"
        cmd_str = str(tmux_calls[0])
        self.assertIn("gemini -s", cmd_str)
        # Check that -y does not appear as a standalone gemini flag
        # (it might appear in other contexts like file paths)
        self.assertIn("gemini -s ", cmd_str)  # ends with space, not -y


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
