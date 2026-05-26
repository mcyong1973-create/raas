#!/usr/bin/env python3
"""
RaaS License Server — Stripe webhook handler.
Receives Stripe payment events, generates license keys, pushes to GitHub.
"""
import json
import os
import uuid
import base64
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_QDaevtGDcITZx6h5rg7AGnz3eRKsacpI")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "mcyong1973-create/raas"
LICENSE_FILE = "license-keys.json"
PORT = int(os.environ.get("PORT", 8443))

import stripe
stripe.api_key = STRIPE_SECRET_KEY

PRICE_MAP = {
    "price_basic": {"tier": "basic", "agents": 2, "price": 1999, "label": "Basic"},
    "price_pro": {"tier": "pro", "agents": 10, "price": 6999, "label": "Pro"},
    "price_enterprise": {"tier": "enterprise", "agents": -1, "price": 49900, "label": "Enterprise"},
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
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "raas-license-server"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/stripe-webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(content_length)
            sig_header = self.headers.get("Stripe-Signature", "")
            
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, STRIPE_WEBHOOK_SECRET
                )
                event_type = event["type"]
                print(f"  Verified Stripe event: {event_type}")
                
                if event_type == "checkout.session.completed":
                    session = event["data"]["object"]
                    customer_email = session.get("customer_details", {}).get("email", "unknown")
                    customer_name = session.get("customer_details", {}).get("name", "Customer")
                    metadata = session.get("metadata", {})
                    price_id = metadata.get("price_id", "price_basic")
                    tier_info = PRICE_MAP.get(price_id, PRICE_MAP["price_basic"])

                    license_key = generate_license_key()

                    keys_path = os.path.join(os.path.dirname(__file__), "license-keys.json")
                    if os.path.exists(keys_path):
                        with open(keys_path) as f:
                            license_data = json.load(f)
                    else:
                        license_data = {"version": 3, "pricing": {}, "keys": {}}
                    
                    license_data["keys"][license_key] = {
                        "client": customer_email,
                        "name": customer_name,
                        "issued": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "agents": tier_info["agents"],
                        "tier": tier_info["tier"],
                        "type": "one-time",
                        "stripe-customer-id": session.get("customer", "")
                    }
                    
                    with open(keys_path, "w") as f:
                        json.dump(license_data, f, indent=2)
                    
                    result = push_to_github(license_data)
                    
                    if result:
                        print(f"  License key {license_key} created for {customer_email}")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "status": "ok",
                            "license-key": license_key,
                            "customer": customer_email
                        }).encode())
                    else:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "GitHub push failed"}).encode())
                
                elif event_type == "customer.subscription.deleted":
                    print(f"  Subscription cancelled. Removing license key...")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "cancelled"}).encode())
                
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ignored"}).encode())
            
            except stripe.error.SignatureVerificationError as e:
                print(f"  Invalid signature: {e}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid signature"}).encode())
            except Exception as e:
                print(f"  Error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    print(f"  RaaS License Server starting on port {PORT}")
    print(f"  Webhook: http://localhost:{PORT}/stripe-webhook")
    print(f"  Public:  https://diabolic-gown-hybrid.ngrok-free.dev/stripe-webhook")
    print()
    
    server = HTTPServer(("0.0.0.0", PORT), LicenseHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
