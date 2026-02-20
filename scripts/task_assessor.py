#!/usr/bin/env python3
import os
import subprocess
import sys

class TaskAssessor:
    def __init__(self, task_folder):
        self.task_folder = task_folder
        self.task_md_path = os.path.join(task_folder, "task.md")

    def assess(self):
        if not os.path.exists(self.task_md_path):
            return "DECOMPOSABLE"  # Default to decomposable if no task.md

        with open(self.task_md_path, "r") as f:
            task_content = f.read()

        # Simple prompt for Gemini
        prompt = f"""
        Read this task and decide if it is "TERMINAL" or "DECOMPOSABLE".
        
        "TERMINAL": The task is atomic enough that it can be completed with a relatively trivial amount of effort and cannot be meaningfully decomposed further.
        "DECOMPOSABLE": The task can and should be broken into subtasks.
        
        Task:
        {task_content}
        
        Answer with only one word: "TERMINAL" or "DECOMPOSABLE".
        """
        
        try:
            # Use gemini command to get the decision
            result = subprocess.run(
                ["gemini", "-s", "-y", "-p", prompt],
                capture_output=True,
                text=True,
                check=True
            )
            decision = result.stdout.strip().upper()
            if "TERMINAL" in decision:
                # Create TERMINAL_TASK marker
                terminal_marker = os.path.join(self.task_folder, "TERMINAL_TASK")
                with open(terminal_marker, "a"):
                    os.utime(terminal_marker, None)
                return "TERMINAL"
            else:
                return "DECOMPOSABLE"
        except Exception as e:
            # Fallback or error
            print(f"Error assessing task: {e}")
            return "DECOMPOSABLE"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 task_assessor.py <task_folder>")
        sys.exit(1)
    
    assessor = TaskAssessor(sys.argv[1])
    print(assessor.assess())
