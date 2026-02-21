#!/usr/bin/env python3
"""
Task Board: Shared task management for Pickle Rick agent teams.

Provides a JSON-file-based task board where agents can create, claim,
update, and list tasks. Supports task dependencies (blocks/blockedBy).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
try:
    from filelock import FileLock, Timeout
except ImportError:
    FileLock = None
    Timeout = Exception


class TaskBoard:
    """Shared task board backed by a single JSON file with file locking."""

    def __init__(self, team_dir):
        self.team_dir = Path(team_dir)
        self.tasks_file = self.team_dir / "tasks.json"
        self.lock_file = self.team_dir / "tasks.json.lock"
        self._ensure_file()

    def _ensure_file(self):
        self.team_dir.mkdir(parents=True, exist_ok=True)
        if not self.tasks_file.exists():
            self.tasks_file.write_text(json.dumps({"next_id": 1, "tasks": {}}, indent=2))

    def _read(self):
        try:
            return json.loads(self.tasks_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {"next_id": 1, "tasks": {}}

    def _write(self, data):
        self.tasks_file.write_text(json.dumps(data, indent=2))

    def _with_lock(self, fn):
        """Execute fn with file lock. Falls back to no lock if filelock unavailable."""
        try:
            lock = FileLock(str(self.lock_file), timeout=5)
            with lock:
                return fn()
        except (Timeout, Exception):
            # Fallback: operate without lock (best effort)
            return fn()

    def create(self, subject, description="", owner=None, blocked_by=None):
        """Create a new task. Returns the task ID."""
        def _do():
            data = self._read()
            task_id = str(data["next_id"])
            data["next_id"] += 1
            data["tasks"][task_id] = {
                "id": task_id,
                "subject": subject,
                "description": description,
                "status": "pending",
                "owner": owner,
                "blocked_by": blocked_by or [],
                "blocks": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            # Update reverse dependencies
            for dep_id in (blocked_by or []):
                if dep_id in data["tasks"]:
                    if task_id not in data["tasks"][dep_id]["blocks"]:
                        data["tasks"][dep_id]["blocks"].append(task_id)
            self._write(data)
            return task_id
        return self._with_lock(_do)

    def update(self, task_id, **kwargs):
        """Update a task. Supported fields: status, subject, description, owner."""
        def _do():
            data = self._read()
            if task_id not in data["tasks"]:
                raise ValueError(f"Task {task_id} not found")
            task = data["tasks"][task_id]
            for key in ("status", "subject", "description", "owner"):
                if key in kwargs:
                    task[key] = kwargs[key]
            if "add_blocked_by" in kwargs:
                for dep_id in kwargs["add_blocked_by"]:
                    if dep_id not in task["blocked_by"]:
                        task["blocked_by"].append(dep_id)
                    if dep_id in data["tasks"]:
                        if task_id not in data["tasks"][dep_id]["blocks"]:
                            data["tasks"][dep_id]["blocks"].append(task_id)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write(data)
            return task
        return self._with_lock(_do)

    def get(self, task_id):
        """Get a task by ID."""
        data = self._read()
        if task_id not in data["tasks"]:
            raise ValueError(f"Task {task_id} not found")
        return data["tasks"][task_id]

    def list_all(self, status=None, owner=None):
        """List tasks, optionally filtered by status and/or owner."""
        data = self._read()
        tasks = list(data["tasks"].values())
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        if owner:
            tasks = [t for t in tasks if t.get("owner") == owner]
        return sorted(tasks, key=lambda t: int(t["id"]))

    def list_available(self):
        """List tasks that are pending, unowned, and not blocked."""
        data = self._read()
        available = []
        for task in data["tasks"].values():
            if task["status"] != "pending" or task.get("owner"):
                continue
            # Check if all blockers are completed
            blocked = False
            for dep_id in task.get("blocked_by", []):
                dep = data["tasks"].get(dep_id)
                if dep and dep["status"] != "completed":
                    blocked = True
                    break
            if not blocked:
                available.append(task)
        return sorted(available, key=lambda t: int(t["id"]))

    def claim(self, task_id, owner):
        """Claim an available task."""
        return self.update(task_id, owner=owner, status="in_progress")

    def complete(self, task_id):
        """Mark a task as completed."""
        return self.update(task_id, status="completed")

    def delete(self, task_id):
        """Delete a task."""
        def _do():
            data = self._read()
            if task_id in data["tasks"]:
                # Remove from blocks lists
                task = data["tasks"][task_id]
                for dep_id in task.get("blocked_by", []):
                    if dep_id in data["tasks"]:
                        blocks = data["tasks"][dep_id].get("blocks", [])
                        if task_id in blocks:
                            blocks.remove(task_id)
                del data["tasks"][task_id]
                self._write(data)
        return self._with_lock(_do)


def main():
    """CLI interface for the task board."""
    import argparse

    parser = argparse.ArgumentParser(description="Task Board CLI")
    parser.add_argument("--team-dir", required=True, help="Path to team directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_p = subparsers.add_parser("create", help="Create a task")
    create_p.add_argument("--subject", required=True)
    create_p.add_argument("--description", default="")
    create_p.add_argument("--owner", default=None)
    create_p.add_argument("--blocked-by", nargs="*", default=[])

    # List
    list_p = subparsers.add_parser("list", help="List tasks")
    list_p.add_argument("--status", default=None)
    list_p.add_argument("--owner", default=None)
    list_p.add_argument("--available", action="store_true")

    # Get
    get_p = subparsers.add_parser("get", help="Get a task")
    get_p.add_argument("--id", required=True)

    # Update
    update_p = subparsers.add_parser("update", help="Update a task")
    update_p.add_argument("--id", required=True)
    update_p.add_argument("--status", default=None)
    update_p.add_argument("--owner", default=None)
    update_p.add_argument("--subject", default=None)

    # Claim
    claim_p = subparsers.add_parser("claim", help="Claim a task")
    claim_p.add_argument("--id", required=True)
    claim_p.add_argument("--owner", required=True)

    # Complete
    complete_p = subparsers.add_parser("complete", help="Complete a task")
    complete_p.add_argument("--id", required=True)

    # Delete
    delete_p = subparsers.add_parser("delete", help="Delete a task")
    delete_p.add_argument("--id", required=True)

    args = parser.parse_args()
    board = TaskBoard(args.team_dir)

    if args.command == "create":
        task_id = board.create(args.subject, args.description, args.owner, args.blocked_by)
        print(json.dumps({"status": "created", "id": task_id}))

    elif args.command == "list":
        if args.available:
            tasks = board.list_available()
        else:
            tasks = board.list_all(status=args.status, owner=args.owner)
        print(json.dumps(tasks, indent=2))

    elif args.command == "get":
        task = board.get(args.id)
        print(json.dumps(task, indent=2))

    elif args.command == "update":
        kwargs = {}
        if args.status:
            kwargs["status"] = args.status
        if args.owner:
            kwargs["owner"] = args.owner
        if args.subject:
            kwargs["subject"] = args.subject
        task = board.update(args.id, **kwargs)
        print(json.dumps(task, indent=2))

    elif args.command == "claim":
        task = board.claim(args.id, args.owner)
        print(json.dumps(task, indent=2))

    elif args.command == "complete":
        task = board.complete(args.id)
        print(json.dumps(task, indent=2))

    elif args.command == "delete":
        board.delete(args.id)
        print(json.dumps({"status": "deleted", "id": args.id}))


if __name__ == "__main__":
    main()
