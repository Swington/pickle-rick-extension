import unittest
from unittest.mock import patch, MagicMock, call
import urllib.error
import sys
import io
import json

# Add the scripts directory to the path so we can import ask_claude
sys.path.append("/Users/switon/.gemini/extensions/pickle-rick/scripts")
import ask_claude

class TestRetryLogic(unittest.TestCase):

    @patch("ask_claude.get_access_token")
    @patch("urllib.request.urlopen")
    @patch("time.sleep") # Don't actually sleep during tests
    def test_retry_on_429_streaming(self, mock_sleep, mock_urlopen, mock_get_token):
        # Setup mocks
        mock_get_token.return_value = "fake-token"
        
        # Mock 429 error followed by success
        error_429 = urllib.error.HTTPError(
            url="http://fake", code=429, msg="Too Many Requests", hdrs={}, fp=io.BytesIO(b"Rate limit exceeded")
        )
        
        # Successful response (streaming)
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [
            b'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Success after retry"}}\n',
            b'data: {"type": "message_stop"}\n'
        ]
        mock_response.__enter__.return_value = mock_response
        
        # Set side effect: first call raises error, second returns success
        mock_urlopen.side_effect = [error_429, mock_response]
        
        # Mock sys.argv
        with patch.object(sys, 'argv', ['ask_claude.py', 'Hi']):
            # Capture stdout to verify output
            with patch('sys.stdout', new=io.StringIO()) as fake_out:
                ask_claude.main()
                output = fake_out.getvalue()
        
        # Verify
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIn("Success after retry", output)
        mock_sleep.assert_called_once()
        print("Test passed: Retried on 429 (streaming) and succeeded.")

    @patch("ask_claude.get_access_token")
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_retry_on_500_non_streaming(self, mock_sleep, mock_urlopen, mock_get_token):
        # Setup mocks
        mock_get_token.return_value = "fake-token"
        
        # Mock 500 error followed by success
        error_500 = urllib.error.HTTPError(
            url="http://fake", code=500, msg="Internal Server Error", hdrs={}, fp=io.BytesIO(b"Server exploded")
        )
        
        # Successful response (non-streaming)
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"content": [{"type": "text", "text": "Success after 500"}]}'
        mock_response.__enter__.return_value = mock_response
        
        # Set side effect: first call raises error, second returns success
        mock_urlopen.side_effect = [error_500, mock_response]
        
        # Mock sys.argv with --no-stream
        with patch.object(sys, 'argv', ['ask_claude.py', 'Hi', '--no-stream']):
            # Capture stdout to verify output
            with patch('sys.stdout', new=io.StringIO()) as fake_out:
                ask_claude.main()
                output = fake_out.getvalue()
        
        # Verify
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIn("Success after 500", output)
        mock_sleep.assert_called_once()
        print("Test passed: Retried on 500 (non-streaming) and succeeded.")

    @patch("ask_claude.get_access_token")
    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_no_retry_on_404(self, mock_sleep, mock_urlopen, mock_get_token):
        # Setup mocks
        mock_get_token.return_value = "fake-token"
        
        # Mock 404 error (should NOT retry)
        error_404 = urllib.error.HTTPError(
            url="http://fake", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b"Resource not found")
        )
        mock_urlopen.side_effect = error_404
        
        # Mock sys.argv
        with patch.object(sys, 'argv', ['ask_claude.py', 'Hi']):
            # sys.exit(1) should be called
            with self.assertRaises(SystemExit) as cm:
                ask_claude.main()
            
            self.assertEqual(cm.exception.code, 1)
        
        # Verify
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()
        print("Test passed: Did not retry on 404.")

if __name__ == "__main__":
    unittest.main()
