#!/usr/bin/env python3
"""
Agent Mailbox: Inter-agent communication system for Pickle Rick teams.

Provides a file-based mailbox system where agents can send direct messages,
broadcast to all teammates, and poll their inbox for new messages.

Messages are stored as JSON files in each agent's inbox directory.
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class AgentMailbox:
    """File-based mailbox for inter-agent communication."""

    def __init__(self, team_dir, agent_name):
        self.team_dir = Path(team_dir)
        self.agent_name = agent_name
        self.mailbox_root = self.team_dir / "mailbox"
        self.inbox = self.mailbox_root / agent_name / "inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def send(self, to, content, msg_type="message"):
        """Send a message to a specific agent."""
        target_inbox = self.mailbox_root / to / "inbox"
        if not target_inbox.exists():
            raise ValueError(f"Agent '{to}' not found in team mailbox")

        msg = {
            "id": str(uuid.uuid4()),
            "from": self.agent_name,
            "to": to,
            "type": msg_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        msg_path = target_inbox / f"{msg['id']}.json"
        msg_path.write_text(json.dumps(msg, indent=2))
        return msg["id"]

    def broadcast(self, content, msg_type="message"):
        """Send a message to all agents in the team (except self)."""
        sent = []
        for agent_dir in self.mailbox_root.iterdir():
            if agent_dir.is_dir() and agent_dir.name != self.agent_name:
                inbox = agent_dir / "inbox"
                if inbox.exists():
                    msg = {
                        "id": str(uuid.uuid4()),
                        "from": self.agent_name,
                        "to": agent_dir.name,
                        "type": msg_type,
                        "content": content,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "read": False,
                    }
                    msg_path = inbox / f"{msg['id']}.json"
                    msg_path.write_text(json.dumps(msg, indent=2))
                    sent.append(agent_dir.name)
        return sent

    def read_inbox(self, unread_only=True, mark_read=True):
        """Read messages from inbox. Returns list sorted by timestamp."""
        messages = []
        for msg_file in self.inbox.glob("*.json"):
            try:
                msg = json.loads(msg_file.read_text())
                if unread_only and msg.get("read", False):
                    continue
                messages.append(msg)
                if mark_read and not msg.get("read", False):
                    msg["read"] = True
                    msg_file.write_text(json.dumps(msg, indent=2))
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(messages, key=lambda m: m.get("timestamp", ""))

    def read_all(self):
        """Read all messages from inbox regardless of read status."""
        return self.read_inbox(unread_only=False, mark_read=False)

    def count_unread(self):
        """Count unread messages without marking them as read."""
        return len(self.read_inbox(unread_only=True, mark_read=False))

    def list_agents(self):
        """List all agents in the team mailbox."""
        agents = []
        for agent_dir in self.mailbox_root.iterdir():
            if agent_dir.is_dir() and (agent_dir / "inbox").exists():
                agents.append(agent_dir.name)
        return sorted(agents)

    @staticmethod
    def create_agent_mailbox(team_dir, agent_name):
        """Create inbox directory for a new agent."""
        inbox = Path(team_dir) / "mailbox" / agent_name / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        return str(inbox)


def main():
    """CLI interface for the mailbox system."""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Mailbox CLI")
    parser.add_argument("--team-dir", required=True, help="Path to team directory")
    parser.add_argument("--agent", required=True, help="Agent name")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Send
    send_parser = subparsers.add_parser("send", help="Send a message")
    send_parser.add_argument("--to", required=True, help="Recipient agent name")
    send_parser.add_argument("--content", required=True, help="Message content")
    send_parser.add_argument("--type", default="message", help="Message type")

    # Broadcast
    bcast_parser = subparsers.add_parser("broadcast", help="Broadcast to all")
    bcast_parser.add_argument("--content", required=True, help="Message content")

    # Read
    read_parser = subparsers.add_parser("read", help="Read inbox")
    read_parser.add_argument("--all", action="store_true", help="Include read messages")

    # Count
    subparsers.add_parser("count", help="Count unread messages")

    # List agents
    subparsers.add_parser("list-agents", help="List team agents")

    args = parser.parse_args()
    mailbox = AgentMailbox(args.team_dir, args.agent)

    if args.command == "send":
        msg_id = mailbox.send(args.to, args.content, args.type)
        print(json.dumps({"status": "sent", "id": msg_id}))

    elif args.command == "broadcast":
        recipients = mailbox.broadcast(args.content)
        print(json.dumps({"status": "broadcast", "recipients": recipients}))

    elif args.command == "read":
        messages = mailbox.read_all() if args.all else mailbox.read_inbox()
        print(json.dumps(messages, indent=2))

    elif args.command == "count":
        print(json.dumps({"unread": mailbox.count_unread()}))

    elif args.command == "list-agents":
        print(json.dumps({"agents": mailbox.list_agents()}))


if __name__ == "__main__":
    main()
