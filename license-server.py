#!/usr/bin/env python3
"""
RaaS License Server — Annual Subscription Management
Generates license keys on Stripe checkout, tracks expiry, agent count, and renewal.
License keys live in license-keys.json on GitHub, pulled by each RaaS instance.
"""
import os
import json
import uuid
import base64
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_QDaevtGDcITZx6h5rg7AGnz3eRKsacpI")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "mcyong1973-create/raas"
LICENSE_FILE = "license-keys.json"
PORT = int(os.environ.get("PORT", 8443))

import stripe
stripe.api_key = STRIPE_SECRET_KEY

# $10/year per license — 365-day subscription
SUBSCRIPTION_DAYS = 365
SUBSCRIPTION_PRICE_CENTS = 1000  # $10.00
MAX_AGENTS = 5  # max agents per license

PRICE_MAP = {
    "price_annual": {
        "tier": "annual",
        "agents": MAX_AGENTS,
        "price": SUBSCRIPTION_PRICE_CENTS,
        "label": "Annual",
        "days": SUBSCRIPTION_DAYS,
    },
}


def generate_license_key():
    """Generate a unique license key."""
    return f"RaaS-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"


def push_to_github(license_keys):
    """Push updated license-keys.json to GitHub."""
    url = f"https://api.github.com/repos/{REPO}/contents/{LICENSE_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "raas-license-server"
    }
    # Get current file SHA
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        current = json.loads(resp.read())
        sha = current.get("sha", "")
    except:
        sha = ""
    # Push update
    content_bytes = json.dumps(license_keys, indent=2).encode()
    content_b64 = base64.b64encode(content_bytes).decode()
    data = json.dumps({
        "message": f"Auto-add license key for new subscriber",
        "content": content_b64,
        "sha": sha
    }).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except Exception as e:
        print(f"  GitHub push failed: {e}")
        return None


class LicenseHandler(BaseHTTPRequestHandler):
    """HTTP server that handles Stripe webhooks for license key management."""
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "raas-license"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/stripe-webhook":
            self.handle_webhook()
        elif self.path == "/renew":
            self.handle_renewal()
        elif self.path == "/check":
            self.handle_check()
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_webhook(self):
        """Handle Stripe checkout.webhook event."""
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)
        sig_header = self.headers.get("Stripe-Signature", "")
        
        if not STRIPE_WEBHOOK_SECRET:
            self.send_error("Stripe webhook secret not configured")
            return
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
            event_type = event["type"]
            print(f"  Verified Stripe event: {event_type}")
            
            if event_type == "checkout.session.completed":
                self.handle_checkout_completed(event)
            elif event_type in ("invoice.paid", "customer.subscription.updated"):
                self.handle_subscription_renewed(event)
            elif event_type == "customer.subscription.deleted":
                self.handle_subscription_cancelled(event)
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ignored", "event": event_type}).encode())
        
        except stripe.error.SignatureVerificationError:
            self.send_error("Signature verification failed", 400)
        except Exception as e:
            self.send_error(f"Webhook error: {e}", 500)
    
    def handle_checkout_completed(self, event):
        """Handle new subscription purchase."""
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email", "unknown")
        customer_name = session.get("customer_details", {}).get("name", "Customer")
        metadata = session.get("metadata", {})
        price_id = metadata.get("price_id", "price_annual")
        tier_info = PRICE_MAP.get(price_id, PRICE_MAP["price_annual"])
        
        license_key = generate_license_key()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=tier_info["days"])
        
        keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
        if os.path.exists(keys_path):
            with open(keys_path) as f:
                license_data = json.load(f)
        else:
            license_data = {"version": 4, "pricing": {}, "keys": {}}
        
        license_data["keys"][license_key] = {
            "client": customer_email,
            "name": customer_name,
            "issued": now.strftime("%Y-%m-%d"),
            "expires": expires.strftime("%Y-%m-%d"),
            "agents": tier_info["agents"],
            "max_agents": tier_info["agents"],
            "registered_agents": [],
            "tier": tier_info["tier"],
            "type": "subscription",
            "auto_renew": True,
            "stripe-customer-id": session.get("customer", ""),
            "stripe-subscription-id": session.get("subscription", ""),
        }
        
        with open(keys_path, "w") as f:
            json.dump(license_data, f, indent=2)
        
        result = push_to_github(license_data)
        
        if result:
            print(f"  License key {license_key} created for {customer_email}, expires {expires.strftime('%Y-%m-%d')}")
            self.send_json({
                "status": "ok",
                "license-key": license_key,
                "customer": customer_email,
                "expires": expires.strftime("%Y-%m-%d"),
                "max_agents": tier_info["agents"],
            })
        else:
            self.send_error("GitHub push failed", 500)
    
    def handle_subscription_renewed(self, event):
        """Extend expiry on successful renewal payment."""
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer", "")
        current_period_end = subscription.get("current_period_end", 0)
        new_expiry = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
        
        # Find and update the matching license key
        keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
        if not os.path.exists(keys_path):
            self.send_error("No license data found", 500)
            return
        
        with open(keys_path) as f:
            license_data = json.load(f)
        
        updated = False
        for key, info in license_data.get("keys", {}).items():
            if info.get("stripe-customer-id") == customer_id:
                info["expires"] = new_expiry.strftime("%Y-%m-%d")
                info["auto_renew"] = True
                updated = True
                print(f"  License {key} renewed, new expiry: {new_expiry.strftime('%Y-%m-%d')}")
                break
        
        if updated:
            with open(keys_path, "w") as f:
                json.dump(license_data, f, indent=2)
            push_to_github(license_data)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())
    
    def handle_subscription_cancelled(self, event):
        """Mark license as not auto-renewing when subscription is cancelled."""
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer", "")
        
        keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
        if not os.path.exists(keys_path):
            self.send_response(200)
            self.end_headers()
            return
        
        with open(keys_path) as f:
            license_data = json.load(f)
        
        for key, info in license_data.get("keys", {}).items():
            if info.get("stripe-customer-id") == customer_id:
                info["auto_renew"] = False
                print(f"  License {key} cancelled — will expire on {info.get('expires', 'unknown')}")
                break
        
        with open(keys_path, "w") as f:
            json.dump(license_data, f, indent=2)
        push_to_github(license_data)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "cancelled"}).encode())
    
    def handle_renewal(self):
        """Manual renewal endpoint — updates expiry by 1 year."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}
        license_key = body.get("license_key", "")
        
        keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
        if not os.path.exists(keys_path):
            self.send_error("No license data", 500)
            return
        
        with open(keys_path) as f:
            license_data = json.load(f)
        
        if license_key not in license_data.get("keys", {}):
            self.send_error("Invalid license key", 404)
            return
        
        info = license_data["keys"][license_key]
        now = datetime.now(timezone.utc)
        current_expiry = datetime.strptime(info["expires"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        # Extend by 1 year from current expiry
        new_expiry = max(current_expiry, now) + timedelta(days=SUBSCRIPTION_DAYS)
        info["expires"] = new_expiry.strftime("%Y-%m-%d")
        
        with open(keys_path, "w") as f:
            json.dump(license_data, f, indent=2)
        push_to_github(license_data)
        
        self.send_json({
            "status": "ok",
            "license-key": license_key,
            "new-expiry": info["expires"],
        })
    
    def handle_check(self):
        """Check license status — used by RaaS engine at startup."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}
        license_key = body.get("license_key", "")
        agent_count = body.get("agent_count", 0)
        
        keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
        if not os.path.exists(keys_path):
            self.send_json({"valid": False, "reason": "no-license-data"})
            return
        
        with open(keys_path) as f:
            license_data = json.load(f)
        
        if license_key not in license_data.get("keys", {}):
            self.send_json({"valid": False, "reason": "invalid-key"})
            return
        
        info = license_data["keys"][license_key]
        now = datetime.now(timezone.utc)
        
        try:
            expires = datetime.strptime(info["expires"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            self.send_json({"valid": False, "reason": "bad-expiry"})
            return
        
        if now > expires:
            self.send_json({
                "valid": False,
                "reason": "expired",
                "expired_since": info["expires"],
                "message": f"License expired {info['expires']}. Renew at support@aion-nation.com",
            })
            return
        
        max_agents = info.get("max_agents", 5)
        if agent_count > max_agents:
            self.send_json({
                "valid": True,
                "limit_exceeded": True,
                "max_agents": max_agents,
                "current_agents": agent_count,
                "message": f"Agent limit exceeded: {agent_count} agents registered, max {max_agents}",
            })
            return
        
        days_left = (expires - now).days
        self.send_json({
            "valid": True,
            "client": info.get("client", "unknown"),
            "expires": info["expires"],
            "days_left": days_left,
            "max_agents": max_agents,
            "tier": info.get("tier", "annual"),
            "auto_renew": info.get("auto_renew", False),
        })
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error(self, message, status=500):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())


def main():
    print("RaaS License Server v2 — Annual Subscription Manager")
    print(f"  Port: {PORT}")
    print(f"  Price: ${SUBSCRIPTION_PRICE_CENTS/100:.2f}/year")
    print(f"  Max agents: {MAX_AGENTS}")
    print(f"  License file: {LICENSE_FILE}")
    print(f"  Webhook: http://localhost:{PORT}/stripe-webhook")
    print()
    print("  Create a Stripe product with:")
    print(f"    - Price: ${SUBSCRIPTION_PRICE_CENTS/100:.2f}")
    print(f"    - Interval: year")
    print(f"    - Metadata: price_id=price_annual")
    print()
    print("  Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in .env")
    print()
    server = HTTPServer(("0.0.0.0", PORT), LicenseHandler)
    print(f"  Listening on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
