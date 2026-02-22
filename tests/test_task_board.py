#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from task_board import TaskBoard


class TestTaskBoard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.board = TaskBoard(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_task(self):
        task_id = self.board.create("Implement feature X", "Details here")
        self.assertEqual(task_id, "1")

        task = self.board.get(task_id)
        self.assertEqual(task["subject"], "Implement feature X")
        self.assertEqual(task["description"], "Details here")
        self.assertEqual(task["status"], "pending")
        self.assertIsNone(task["owner"])

    def test_create_multiple_tasks_increments_id(self):
        id1 = self.board.create("Task 1")
        id2 = self.board.create("Task 2")
        id3 = self.board.create("Task 3")
        self.assertEqual(id1, "1")
        self.assertEqual(id2, "2")
        self.assertEqual(id3, "3")

    def test_list_all_tasks(self):
        self.board.create("Task 1")
        self.board.create("Task 2")
        self.board.create("Task 3")

        tasks = self.board.list_all()
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["subject"], "Task 1")
        self.assertEqual(tasks[2]["subject"], "Task 3")

    def test_list_by_status(self):
        self.board.create("Task 1")
        id2 = self.board.create("Task 2")
        self.board.update(id2, status="in_progress")

        pending = self.board.list_all(status="pending")
        in_progress = self.board.list_all(status="in_progress")
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(in_progress), 1)

    def test_list_by_owner(self):
        id1 = self.board.create("Task 1", owner="agent-1")
        id2 = self.board.create("Task 2", owner="agent-2")
        id3 = self.board.create("Task 3")

        agent1_tasks = self.board.list_all(owner="agent-1")
        self.assertEqual(len(agent1_tasks), 1)
        self.assertEqual(agent1_tasks[0]["id"], id1)

    def test_claim_task(self):
        task_id = self.board.create("Task 1")
        task = self.board.claim(task_id, "agent-1")

        self.assertEqual(task["owner"], "agent-1")
        self.assertEqual(task["status"], "in_progress")

    def test_complete_task(self):
        task_id = self.board.create("Task 1")
        self.board.claim(task_id, "agent-1")
        task = self.board.complete(task_id)

        self.assertEqual(task["status"], "completed")

    def test_delete_task(self):
        task_id = self.board.create("Task 1")
        self.board.delete(task_id)

        with self.assertRaises(ValueError):
            self.board.get(task_id)

    def test_task_dependencies(self):
        id1 = self.board.create("Setup infrastructure")
        id2 = self.board.create("Build feature", blocked_by=[id1])

        task1 = self.board.get(id1)
        task2 = self.board.get(id2)

        self.assertIn(id2, task1["blocks"])
        self.assertIn(id1, task2["blocked_by"])

    def test_list_available_excludes_blocked(self):
        id1 = self.board.create("Setup infrastructure")
        id2 = self.board.create("Build feature", blocked_by=[id1])
        id3 = self.board.create("Write docs")

        available = self.board.list_available()
        available_ids = [t["id"] for t in available]

        self.assertIn(id1, available_ids)
        self.assertIn(id3, available_ids)
        self.assertNotIn(id2, available_ids)  # blocked

    def test_list_available_includes_unblocked_after_completion(self):
        id1 = self.board.create("Setup infrastructure")
        id2 = self.board.create("Build feature", blocked_by=[id1])

        # Initially task 2 is blocked
        available = self.board.list_available()
        self.assertEqual(len(available), 1)

        # Complete task 1
        self.board.claim(id1, "agent-1")
        self.board.complete(id1)

        # Now task 2 should be available
        available = self.board.list_available()
        available_ids = [t["id"] for t in available]
        self.assertIn(id2, available_ids)

    def test_list_available_excludes_owned(self):
        id1 = self.board.create("Task 1", owner="agent-1")
        id2 = self.board.create("Task 2")

        available = self.board.list_available()
        available_ids = [t["id"] for t in available]
        self.assertNotIn(id1, available_ids)
        self.assertIn(id2, available_ids)

    def test_update_nonexistent_task_raises(self):
        with self.assertRaises(ValueError):
            self.board.update("999", status="completed")

    def test_get_nonexistent_task_raises(self):
        with self.assertRaises(ValueError):
            self.board.get("999")

    def test_delete_removes_from_blocks(self):
        id1 = self.board.create("Task 1")
        id2 = self.board.create("Task 2", blocked_by=[id1])

        # Verify dependency exists
        task1 = self.board.get(id1)
        self.assertIn(id2, task1["blocks"])

        # Delete task 2
        self.board.delete(id2)

        # Task 1's blocks should no longer contain task 2
        task1 = self.board.get(id1)
        self.assertNotIn(id2, task1["blocks"])

    def test_task_has_timestamps(self):
        task_id = self.board.create("Task 1")
        task = self.board.get(task_id)

        self.assertIn("created_at", task)
        self.assertIn("updated_at", task)

    def test_update_changes_updated_at(self):
        task_id = self.board.create("Task 1")
        task_before = self.board.get(task_id)

        import time
        time.sleep(0.01)  # Ensure timestamp differs

        self.board.update(task_id, subject="Updated Task 1")
        task_after = self.board.get(task_id)

        self.assertEqual(task_after["subject"], "Updated Task 1")
        self.assertGreaterEqual(task_after["updated_at"], task_before["updated_at"])


if __name__ == "__main__":
    unittest.main()
