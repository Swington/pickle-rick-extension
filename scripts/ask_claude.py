#!/usr/bin/env python3
import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl

def get_access_token():
    """Gets the Google Cloud access token using gcloud."""
    try:
        # Try using gcloud first as it was in the user's example
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to google-auth if gcloud fails or is not found
        try:
            import google.auth
            import google.auth.transport.requests
            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            return creds.token
        except ImportError:
            print("Error: gcloud not found and google-auth not installed.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error getting access token via library: {e}", file=sys.stderr)
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Query Claude Sonnet on Vertex AI")
    parser.add_argument("prompt", help="The prompt to send to Claude")
    parser.add_argument("--project", default=os.environ.get("GCP_PROJECT", "switon-gsd-demos"), help="GCP Project ID")
    parser.add_argument("--location", default=os.environ.get("GCP_LOCATION", "global"), help="GCP Location (e.g., us-central1, global)")
    parser.add_argument("--model", default="claude-sonnet-4-5", help="Model ID")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.5, help="Temperature") # Lower temp for coding
    parser.add_argument("--stream", action=argparse.BooleanOptionalAction, default=True, help="Stream the response")

    args = parser.parse_args()

    token = get_access_token()
    
    endpoint = "aiplatform.googleapis.com"
    method = "streamRawPredict" if args.stream else "rawPredict"
    
    url = f"https://{endpoint}/v1/projects/{args.project}/locations/{args.location}/publishers/anthropic/models/{args.model}:{method}"
    
    payload = {
        "anthropic_version": "vertex-2023-10-16",
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": args.stream,
        "messages": [
            {
                "role": "user",
                "content": args.prompt
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    
    # Bypass SSL verification for local dev environments with broken cert stores
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    MAX_RETRIES = 5
    BASE_DELAY = 2

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                if args.stream:
                    # Streaming response processing (Server-Sent Events)
                    for line in response:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data:"):
                            data_str = line[5:].strip() # Remove 'data:' prefix
                            if not data_str:
                                continue
                            try:
                                data = json.loads(data_str)
                                # Anthropic stream format: type: "content_block_delta", delta: {type: "text_delta", text: "..."}
                                event_type = data.get("type")
                                if event_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        print(text, end="", flush=True)
                                elif event_type == "message_stop":
                                    break
                                elif event_type == "error":
                                    print(f"\nAPI Error: {data.get('error')}", file=sys.stderr)
                            except json.JSONDecodeError:
                                pass # Skip invalid JSON lines
                else:
                    # Non-streaming
                    response_body = response.read().decode("utf-8")
                    data = json.loads(response_body)
                    # Parse standard response
                    for content in data.get("content", []):
                        if content.get("type") == "text":
                            print(content.get("text", ""))
                return # Success

        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    print(f"\nTransient error {e.code}. Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(delay)
                    continue
            
            print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
            try:
                print(e.read().decode("utf-8"), file=sys.stderr)
            except:
                pass
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
