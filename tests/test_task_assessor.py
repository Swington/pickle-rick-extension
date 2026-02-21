import unittest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import sys

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

class TestTaskAssessor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.task_folder = os.path.join(self.test_dir, "my-task")
        os.makedirs(self.task_folder)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    def test_terminal_task_creation(self, mock_run):
        # Mock gemini call to return "TERMINAL"
        mock_run.return_value = MagicMock(returncode=0, stdout="TERMINAL")
        
        task_md_path = os.path.join(self.task_folder, "task.md")
        with open(task_md_path, "w") as f:
            f.write("# Task: Write Hello World\nWrite a simple hello world script.")
            
        import task_assessor
        assessor = task_assessor.TaskAssessor(self.task_folder)
        result = assessor.assess()
        
        self.assertEqual(result, "TERMINAL")
        self.assertTrue(os.path.exists(os.path.join(self.task_folder, "TERMINAL_TASK")))

    @patch("subprocess.run")
    def test_decomposable_task_no_creation(self, mock_run):
        # Mock gemini call to return "DECOMPOSABLE"
        mock_run.return_value = MagicMock(returncode=0, stdout="DECOMPOSABLE")
        
        task_md_path = os.path.join(self.task_folder, "task.md")
        with open(task_md_path, "w") as f:
            f.write("# Task: Build a Search Engine\nImplement a full search engine from scratch.")
            
        import task_assessor
        assessor = task_assessor.TaskAssessor(self.task_folder)
        result = assessor.assess()
        
        self.assertEqual(result, "DECOMPOSABLE")
        self.assertFalse(os.path.exists(os.path.join(self.task_folder, "TERMINAL_TASK")))

if __name__ == "__main__":
    unittest.main()
