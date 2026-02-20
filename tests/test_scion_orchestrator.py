import unittest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import sys

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

# We will implement scion_orchestrator in scripts/scion_orchestrator.py
# For now, we mock the import if it doesn't exist yet, but we will write it soon.
try:
    import scion_orchestrator
except ImportError:
    pass

class TestScionOrchestrator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.task_folder = os.path.join(self.test_dir, "my-task")
        os.makedirs(os.path.join(self.task_folder, "subtasks", "00-task-1"))
        os.makedirs(os.path.join(self.task_folder, "subtasks", "00-task-2"))
        os.makedirs(os.path.join(self.task_folder, "subtasks", "01-task-3"))
        
        with open(os.path.join(self.task_folder, "task.md"), "w") as f:
            f.write("# Parent Task
Some description.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("time.sleep", return_value=None)
    def test_orchestration_loop(self, mock_sleep, mock_check_output, mock_run):
        # Mock scion start (subprocess.run)
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock scion ls --format json (subprocess.check_output)
        # First call: agents are running
        # Second call: agents are completed
        running_agents = [
            {"name": "00-task-1", "sessionStatus": "RUNNING"},
            {"name": "00-task-2", "sessionStatus": "RUNNING"}
        ]
        completed_agents = [
            {"name": "00-task-1", "sessionStatus": "COMPLETED"},
            {"name": "00-task-2", "sessionStatus": "COMPLETED"},
            {"name": "01-task-3", "sessionStatus": "COMPLETED"}
        ]
        
        mock_check_output.side_effect = [
            json.dumps(running_agents).encode(), # Poll 1 (Group 00)
            json.dumps(completed_agents).encode(), # Poll 2 (Group 00)
            json.dumps(completed_agents).encode()  # Group 01
        ]
        
        # This is where we would call our orchestrator's main logic
        import scion_orchestrator
        orchestrator = scion_orchestrator.ScionOrchestrator(self.task_folder)
        orchestrator.run()
        
        # Verify scion start was called for each subtask
        self.assertEqual(mock_run.call_count, 3)
        
        # Check if children.txt was created
        children_file = os.path.join(self.task_folder, "children.txt")
        self.assertTrue(os.path.exists(children_file))
        with open(children_file, "r") as f:
            children = f.read().splitlines()
        self.assertIn("00-task-1", children)
        self.assertIn("00-task-2", children)
        self.assertIn("01-task-3", children)

if __name__ == "__main__":
    unittest.main()
