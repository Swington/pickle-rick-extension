#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from agent_mailbox import AgentMailbox


class TestAgentMailbox(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create mailboxes for 3 agents
        AgentMailbox.create_agent_mailbox(self.test_dir, "manager")
        AgentMailbox.create_agent_mailbox(self.test_dir, "agent-1")
        AgentMailbox.create_agent_mailbox(self.test_dir, "agent-2")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_agent_mailbox(self):
        inbox_path = os.path.join(self.test_dir, "mailbox", "agent-3", "inbox")
        self.assertFalse(os.path.exists(inbox_path))
        AgentMailbox.create_agent_mailbox(self.test_dir, "agent-3")
        self.assertTrue(os.path.exists(inbox_path))

    def test_send_message(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        msg_id = mailbox.send("agent-1", "Hello agent-1", msg_type="message")
        self.assertIsNotNone(msg_id)

        # Verify message landed in agent-1's inbox
        agent1 = AgentMailbox(self.test_dir, "agent-1")
        messages = agent1.read_inbox()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["from"], "manager")
        self.assertEqual(messages[0]["to"], "agent-1")
        self.assertEqual(messages[0]["content"], "Hello agent-1")
        self.assertEqual(messages[0]["type"], "message")

    def test_send_to_nonexistent_agent_raises(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        with self.assertRaises(ValueError):
            mailbox.send("nonexistent", "Hello")

    def test_broadcast(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        recipients = mailbox.broadcast("Team announcement")

        self.assertIn("agent-1", recipients)
        self.assertIn("agent-2", recipients)
        self.assertNotIn("manager", recipients)  # Should not send to self

        # Verify both agents received the message
        agent1 = AgentMailbox(self.test_dir, "agent-1")
        agent2 = AgentMailbox(self.test_dir, "agent-2")
        self.assertEqual(len(agent1.read_inbox()), 1)
        self.assertEqual(len(agent2.read_inbox()), 1)

    def test_read_marks_as_read(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        mailbox.send("agent-1", "First message")

        agent1 = AgentMailbox(self.test_dir, "agent-1")

        # First read returns the message
        messages = agent1.read_inbox(unread_only=True, mark_read=True)
        self.assertEqual(len(messages), 1)

        # Second read returns nothing (already read)
        messages = agent1.read_inbox(unread_only=True, mark_read=True)
        self.assertEqual(len(messages), 0)

    def test_read_all_includes_read_messages(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        mailbox.send("agent-1", "Message 1")

        agent1 = AgentMailbox(self.test_dir, "agent-1")
        agent1.read_inbox()  # Mark as read

        # read_all should still return it
        all_messages = agent1.read_all()
        self.assertEqual(len(all_messages), 1)

    def test_count_unread(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        mailbox.send("agent-1", "Message 1")
        mailbox.send("agent-1", "Message 2")
        mailbox.send("agent-1", "Message 3")

        agent1 = AgentMailbox(self.test_dir, "agent-1")
        self.assertEqual(agent1.count_unread(), 3)

        # Read one
        agent1.read_inbox()
        self.assertEqual(agent1.count_unread(), 0)

    def test_list_agents(self):
        mailbox = AgentMailbox(self.test_dir, "manager")
        agents = mailbox.list_agents()
        self.assertEqual(sorted(agents), ["agent-1", "agent-2", "manager"])

    def test_messages_sorted_by_timestamp(self):
        agent1 = AgentMailbox(self.test_dir, "agent-1")
        manager = AgentMailbox(self.test_dir, "manager")

        # Send multiple messages
        manager.send("agent-1", "First")
        manager.send("agent-1", "Second")
        manager.send("agent-1", "Third")

        messages = agent1.read_inbox()
        self.assertEqual(len(messages), 3)
        # Timestamps should be in order
        for i in range(len(messages) - 1):
            self.assertLessEqual(messages[i]["timestamp"], messages[i + 1]["timestamp"])

    def test_bidirectional_communication(self):
        manager = AgentMailbox(self.test_dir, "manager")
        agent1 = AgentMailbox(self.test_dir, "agent-1")

        # Manager sends to agent
        manager.send("agent-1", "Do this task")

        # Agent reads and replies
        msgs = agent1.read_inbox()
        self.assertEqual(msgs[0]["content"], "Do this task")
        agent1.send("manager", "Task done")

        # Manager reads reply
        replies = manager.read_inbox()
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["content"], "Task done")
        self.assertEqual(replies[0]["from"], "agent-1")

    def test_shutdown_request_message_type(self):
        manager = AgentMailbox(self.test_dir, "manager")
        manager.send("agent-1", "Shutting down", msg_type="shutdown_request")

        agent1 = AgentMailbox(self.test_dir, "agent-1")
        msgs = agent1.read_inbox()
        self.assertEqual(msgs[0]["type"], "shutdown_request")

    def test_peer_to_peer_communication(self):
        agent1 = AgentMailbox(self.test_dir, "agent-1")
        agent2 = AgentMailbox(self.test_dir, "agent-2")

        agent1.send("agent-2", "Review my code please")
        msgs = agent2.read_inbox()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["from"], "agent-1")
        self.assertEqual(msgs[0]["content"], "Review my code please")


if __name__ == "__main__":
    unittest.main()
