#!/usr/bin/env python3
"""
RaaS Notifier — sends alerts when Score E increases.
Checks all agents periodically and sends notifications.

Usage:
  python3 notifier.py              # Check once and report
  python3 notifier.py --watch      # Watch continuously (every 60s)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

RaaS_API = "http://localhost:8080/api/v1"
TRACKER_FILE = os.path.expanduser("~/.raas/score-tracker.json")
SUPPORT_EMAIL = "support@aion-nation.com"

# WhatsApp target (from env or config)
WHATSAPP_TARGET = os.environ.get("RaaS_WHATSAPP", "whatsapp:16044889229")


def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "raas-notifier/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except:
        return None


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            try:
                return json.load(f)
            except:
                pass
    return {}


def save_tracker(tracker):
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def send_whatsapp(message):
    """Send WhatsApp notification via Hermes gateway API."""
    try:
        # Use the Hermes gateway HTTP API
        import urllib.request
        payload = json.dumps({
            "target": WHATSAPP_TARGET,
            "message": message[:2000]
        }).encode()
        req = urllib.request.Request(
            "http://localhost:3000/api/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except:
        pass
    # Fallback: write to notification log
    try:
        with open(os.path.expanduser("~/.raas/notifications.log"), "a") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")
        return True
    except:
        pass
    return False


def check_agent(agent_id):
    """Check a single agent for Score E changes."""
    tracker = load_tracker()
    
    score = fetch_json(f"{RaaS_API}/score/{agent_id}")
    if not score:
        return
    
    new_se = score.get("score-e", 0)
    old_se = tracker.get(agent_id, {}).get("last-score-e", None)
    
    if old_se is None:
        # First time seeing this agent — just record baseline
        tracker[agent_id] = {"last-score-e": new_se}
        save_tracker(tracker)
        return
    
    if new_se > old_se:
        increase = new_se - old_se
        print(f"\n  ⚠ Score E increased for {agent_id}: {old_se} → {new_se} (+{increase})")
        
        # Get error details
        errors_data = fetch_json(f"{RaaS_API}/score/{agent_id}/errors")
        recent_errors = []
        if errors_data:
            errors = errors_data if isinstance(errors_data, list) else errors_data.get("errors", [])
            recent_errors = errors[-3:] if errors else []
        
        # Build message
        msg = f"🛑 RaaS Alert — {agent_id}"
        msg += f"\nScore E: {old_se} → {new_se} (+{increase})"
        msg += f"\nDashboard: http://localhost:8080/agent/{agent_id}"
        for e in recent_errors:
            what = e.get("what", "Unknown")[:100] if isinstance(e, dict) else str(e)[:100]
            msg += f"\n  • {what}"
        msg += f"\nContact: {SUPPORT_EMAIL}"
        
        print(msg)
        
        # Send WhatsApp
        sent = send_whatsapp(msg)
        if sent:
            print(f"  ✓ WhatsApp notification sent")
        else:
            print(f"  ✗ Could not send WhatsApp notification")
        
        # Update tracker
        tracker[agent_id] = {"last-score-e": new_se, "last-notified": datetime.now(timezone.utc).isoformat()}
        save_tracker(tracker)


def check_all_agents():
    """Check all registered agents for Score E changes."""
    agents_data = fetch_json(f"{RaaS_API}/agents")
    if not agents_data:
        print("  ✗ Cannot reach RaaS server")
        return
    
    agents = agents_data.get("agents", [])
    for a in agents:
        check_agent(a.get("agent-id", ""))


def main():
    watch_mode = "--watch" in sys.argv
    
    if watch_mode:
        print(f"  RaaS Notifier — watching agents every 60 seconds")
        print(f"  WhatsApp target: {WHATSAPP_TARGET}")
        print()
        while True:
            check_all_agents()
            time.sleep(60)
    else:
        check_all_agents()


if __name__ == "__main__":
    main()
