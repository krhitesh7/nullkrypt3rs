#!/usr/bin/env python3
"""
Test script for the GitHub webhook server.

This script simulates GitHub webhook events to test your server locally.
"""

import requests
import json
import hmac
import hashlib
import os
from datetime import datetime


def create_signature(payload, secret):
    """Create GitHub webhook signature."""
    if not secret:
        return None
    
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


def test_ping():
    """Test ping event."""
    print("\n" + "="*60)
    print("Testing PING event")
    print("="*60)
    
    payload = {
        "zen": "Design for failure.",
        "hook_id": 12345,
        "hook": {
            "type": "Repository",
            "id": 12345,
            "events": ["pull_request"]
        }
    }
    
    send_webhook("ping", payload)


def test_pr_opened():
    """Test pull_request.opened event."""
    print("\n" + "="*60)
    print("Testing PULL REQUEST OPENED event")
    print("="*60)
    
    payload = {
        "action": "opened",
        "number": 1,
        "pull_request": {
            "number": 1,
            "html_url": "https://github.com/test-owner/test-repo/pull/1",
            "title": "Test PR for security analysis",
            "body": "This is a test pull request to verify the webhook server",
            "state": "open",
            "user": {
                "login": "test-user"
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "base": {
                "ref": "main",
                "sha": "abc123"
            },
            "head": {
                "ref": "feature/test",
                "sha": "def456"
            }
        },
        "repository": {
            "name": "test-repo",
            "full_name": "test-owner/test-repo",
            "owner": {
                "login": "test-owner"
            }
        },
        "sender": {
            "login": "test-user"
        }
    }
    
    send_webhook("pull_request", payload)


def test_pr_synchronize():
    """Test pull_request.synchronize event."""
    print("\n" + "="*60)
    print("Testing PULL REQUEST SYNCHRONIZE event")
    print("="*60)
    
    payload = {
        "action": "synchronize",
        "number": 1,
        "pull_request": {
            "number": 1,
            "html_url": "https://github.com/test-owner/test-repo/pull/1",
            "title": "Test PR - Updated",
            "body": "Updated pull request",
            "state": "open",
            "user": {
                "login": "test-user"
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "base": {
                "ref": "main",
                "sha": "abc123"
            },
            "head": {
                "ref": "feature/test",
                "sha": "ghi789"
            }
        },
        "repository": {
            "name": "test-repo",
            "full_name": "test-owner/test-repo",
            "owner": {
                "login": "test-owner"
            }
        }
    }
    
    send_webhook("pull_request", payload)


def send_webhook(event_type, payload):
    """Send a webhook request to the server."""
    url = os.environ.get("WEBHOOK_URL", "http://localhost:8080/webhook")
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    
    payload_json = json.dumps(payload)
    signature = create_signature(payload_json, secret)
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": event_type,
        "X-GitHub-Delivery": f"test-delivery-{datetime.now().timestamp()}",
        "User-Agent": "GitHub-Hookshot/test"
    }
    
    if signature:
        headers["X-Hub-Signature-256"] = signature
    
    print(f"\nSending {event_type} event to {url}")
    print(f"Payload: {json.dumps(payload, indent=2)[:200]}...")
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 202]:
            print("✅ Test PASSED")
        else:
            print("❌ Test FAILED")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_health():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("Testing HEALTH endpoint")
    print("="*60)
    
    url = os.environ.get("WEBHOOK_URL", "http://localhost:8080/health")
    url = url.replace("/webhook", "/health")
    
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Health check PASSED")
        else:
            print("❌ Health check FAILED")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GitHub Webhook Server Test Suite")
    print("="*60)
    
    webhook_url = os.environ.get("WEBHOOK_URL", "http://localhost:8080/webhook")
    print(f"\nTarget URL: {webhook_url}")
    print(f"Secret configured: {bool(os.environ.get('GITHUB_WEBHOOK_SECRET'))}")
    
    # Run tests
    test_health()
    test_ping()
    
    # Uncomment to test actual PR events (will trigger analysis)
    # WARNING: These will attempt to fetch real PR data from GitHub
    # test_pr_opened()
    # test_pr_synchronize()
    
    print("\n" + "="*60)
    print("Test suite complete!")
    print("="*60)
    print("\nNote: PR event tests are commented out by default.")
    print("Uncomment them in the script to test actual PR analysis.")
    print("Make sure to use a real PR URL that your GITHUB_TOKEN has access to.")


if __name__ == "__main__":
    main()

