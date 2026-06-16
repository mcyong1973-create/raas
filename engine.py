#!/usr/bin/env python3
"""
RaaS Core Engine — Ledger Storage and Serving
Phase 2: Added get_score, get_agent_ledger for new API endpoints.
"""
import json
import os
import uuid
from datetime import datetime, timezone
import urllib.request

AGENTS_DIR = os.path.expanduser("~/aion/ventures/raas/ledgers")
os.makedirs(AGENTS_DIR, exist_ok=True)
LEDGERS_DIR = AGENTS_DIR  # same directory

# Score change tracking — stores last known Score E for each agent
SCORE_TRACKER_PATH = os.path.expanduser("~/.raas/score-tracker.json")

def load_score_tracker():
    if os.path.exists(SCORE_TRACKER_PATH):
        with open(SCORE_TRACKER_PATH) as f:
            try:
                return json.load(f)
            except:
                pass
    return {}

def save_score_tracker(tracker):
    os.makedirs(os.path.dirname(SCORE_TRACKER_PATH), exist_ok=True)
    with open(SCORE_TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2)

def get_score_change(agent_id):
    """Check if Score E increased since last check. Returns (changed, old, new, flags)"""
    tracker = load_score_tracker()
    result, status = get_score(agent_id)
    if status != 200:
        return False, 0, 0, []
    
    new_se = result.get("score-e", 0)
    old_se = tracker.get(agent_id, {}).get("last-score-e", 0)  # Default to 0, not new_se
    
    # Get detailed flag info
    errors_data, _ = get_score_breakdown(agent_id)
    errors = errors_data.get("breakdown", {}).get("errors", [])
    new_flags = []
    if new_se > old_se:
        # Get the most recent errors (up to 3) that contributed to the increase
        new_flags = errors[-3:] if errors else []
    
    # Update tracker
    tracker[agent_id] = {"last-score-e": new_se}
    save_score_tracker(tracker)
    
    changed = new_se > old_se
    return changed, old_se, new_se, new_flags

# License system
LICENSE_URL = "https://raw.githubusercontent.com/mcyong1973-create/raas/main/license-keys.json"
LICENSE_CACHE_PATH = os.path.expanduser("~/.raas/license-cache.json")

def check_license(license_key=None):
    """Check if the license is valid. Caches result for 24 hours."""
    # If no license key in config, check cache
    if not license_key:
        config_path = os.path.expanduser("~/.raas/config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            license_key = config.get("license-key", "")
    
    # Check cache first (valid for 24h)
    if os.path.exists(LICENSE_CACHE_PATH):
        with open(LICENSE_CACHE_PATH) as f:
            try:
                cache = json.load(f)
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cache.get("checked-at", "2000-01-01"))).total_seconds()
                if age < 86400 and cache.get("valid"):
                    return cache  # Cache is fresh
            except:
                pass
    
    # No license key = expired
    if not license_key:
        return {"valid": False, "reason": "no-license", "message": "No license key configured. Run: raas-monitor license <key>"}
    
    # Check with license file from GitHub
    try:
        req = urllib.request.Request(LICENSE_URL, headers={"User-Agent": "raas-license"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        keys = data.get("keys", {})
        
        if license_key in keys:
            key_info = keys[license_key]
            expires = key_info.get("expires", "")
            agents_allowed = key_info.get("max_agents", key_info.get("agents", 5))
            tier = key_info.get("tier", "annual")
            
            # Check expiry
            now = datetime.now(timezone.utc)
            expired = False
            if expires:
                try:
                    exp_date = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    expired = now > exp_date
                except:
                    pass
            
            if expired:
                result = {
                    "valid": False,
                    "reason": "expired",
                    "license-key": license_key,
                    "expires": expires,
                    "message": f"License expired {expires}. Renew at support@aion-nation.com",
                    "agents-allowed": 0,
                }
            else:
                days_left = None
                if expires:
                    try:
                        exp_date = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        days_left = (exp_date - now).days
                    except:
                        pass
                
                result = {
                    "valid": True,
                    "license-key": license_key,
                    "client": key_info.get("client", "Unknown"),
                    "tier": tier,
                    "expires": expires,
                    "days_left": days_left,
                    "agents-allowed": agents_allowed,
                    "message": f"License valid ({tier}). Expires: {expires}. Agents: {agents_allowed}. Days left: {days_left or 'N/A'}"
                }
        else:
            # Check for demo key
            if license_key and license_key.startswith("DEMO-"):
                result = {"valid": True, "license-key": license_key, "client": "Demo", "expires": "2026-06-25", "message": "Demo license active"}
            else:
                result = {"valid": False, "reason": "invalid-key", "message": f"License key '{license_key}' not found. Contact support@aion-nation.com"}
        
        # Cache the result
        os.makedirs(os.path.dirname(LICENSE_CACHE_PATH), exist_ok=True)
        result["checked-at"] = datetime.now(timezone.utc).isoformat()
        with open(LICENSE_CACHE_PATH, "w") as f:
            json.dump(result, f, indent=2)
        
        return result
    except Exception as e:
        # If license server unreachable, fall back to cache
        if os.path.exists(LICENSE_CACHE_PATH):
            with open(LICENSE_CACHE_PATH) as f:
                return json.load(f)
        return {"valid": False, "reason": "unreachable", "message": str(e)}


def verify_license():
    """Verify license before recording new claims. Returns True if allowed."""
    result = check_license()
    if result.get("valid"):
        # Even if the API says valid, check the hard expiry from the cache
        cache_path = LICENSE_CACHE_PATH
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                cache = json.load(f)
            expires_str = cache.get("expires", "")
            if expires_str:
                try:
                    expires_date = datetime.fromisoformat(expires_str)
                    if datetime.now(timezone.utc) > expires_date:
                        return False, "License expired on " + expires_str
                except:
                    pass
            
            # Check agent count limit
            agents_allowed = cache.get("agents-allowed", 2)
            active_count = count_active_agents()
            if active_count > agents_allowed:
                return False, f"Agent limit exceeded ({active_count}/{agents_allowed}). Upgrade your plan."
        
        return True, "valid"
    
    # Grace period: check cache for hard expiry date first
    if os.path.exists(LICENSE_CACHE_PATH):
        with open(LICENSE_CACHE_PATH) as f:
            cache = json.load(f)
        
        expires_str = cache.get("expires", "")
        if expires_str:
            try:
                expires_date = datetime.fromisoformat(expires_str)
                if datetime.now(timezone.utc) > expires_date:
                    return False, "License expired."
            except:
                pass
        
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cache.get("checked-at", "2000-01-01"))).total_seconds()
        if age < 604800:
            return True, "grace"
    
    return False, "No valid license."


def count_active_agents():
    """Count the number of unique registered agents."""
    count = 0
    if os.path.exists(AGENTS_DIR):
        for item in os.listdir(AGENTS_DIR):
            agent_dir = os.path.join(AGENTS_DIR, item)
            if os.path.isdir(agent_dir) and os.path.exists(os.path.join(agent_dir, "meta.json")):
                count += 1
    return count


def get_agent_dir(agent_id):
    return os.path.join(AGENTS_DIR, agent_id)


def register_agent(data):
    agent_id = data.get("agent-id", "").strip()
    if not agent_id:
        return {"error": "agent-id is required"}, 400
    display_name = data.get("display-name", agent_id)
    agent_dir = get_agent_dir(agent_id)
    if os.path.exists(agent_dir):
        return {"error": f"Agent {agent_id} already exists"}, 409
    os.makedirs(agent_dir, exist_ok=True)
    api_key = str(uuid.uuid4())
    meta = {
        "agent-id": agent_id,
        "display-name": display_name,
        "api-key": api_key,
        "created": datetime.now(timezone.utc).isoformat(),
        "last-active": datetime.now(timezone.utc).isoformat(),
        "identity-token": str(uuid.uuid4()),
        "home-instance": os.uname().nodename,
        "reputation-portable": True
    }
    ledger_path = os.path.join(agent_dir, "ledger.jsonl")
    with open(os.path.join(agent_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    with open(ledger_path, "w") as f:
        f.write(f"# Ledger for {display_name} ({agent_id})\n")
        f.write(f"# Created: {meta['created']}\n")
        f.write(f"# Score A: 0  |  Score E: 0\n")
    return {
        "agent-id": agent_id,
        "ledger-url": f"/ledger/{agent_id}",
        "api-key": api_key,
        "identity-token": meta["identity-token"],
        "message": "Agent registered."
    }, 201


def calculate_score(claims):
    score_a = sum(1 for c in claims if c.get("outcome") == "success")
    score_e = sum(1 for c in claims if c.get("mistakes") and len(c["mistakes"]) > 0)
    return score_a, score_e


def _load_meta(agent_id):
    meta_path = os.path.join(LEDGERS_DIR, agent_id, "meta.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path) as f:
        return json.load(f)


def _load_claims(agent_id):
    ledger_path = os.path.join(LEDGERS_DIR, agent_id, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        return []
    claims = []
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    claims.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return claims


def get_score(agent_id):
    """Get an agent's score summary."""
    meta = _load_meta(agent_id)
    if not meta:
        return {"error": "Agent not found"}, 404
    claims = _load_claims(agent_id)
    score_a, score_e = calculate_score(claims)
    return {
        "agent-id": agent_id,
        "display-name": meta.get("display-name", agent_id),
        "score-a": score_a,
        "score-e": score_e,
        "total-claims": len(claims),
        "last-active": meta.get("last-active", "never")
    }, 200


def get_agent_ledger(agent_id):
    """Get an agent's full claim history."""
    meta = _load_meta(agent_id)
    if not meta:
        return {"error": "Agent not found"}, 404
    claims = _load_claims(agent_id)
    return {
        "agent-id": agent_id,
        "display-name": meta.get("display-name", agent_id),
        "total-claims": len(claims),
        "claims": claims
    }, 200


def get_score_breakdown(agent_id):
    """Get a detailed breakdown of why scores are what they are."""
    meta = _load_meta(agent_id)
    if not meta:
        return {"error": "Agent not found"}, 404
    claims = _load_claims(agent_id)
    score_a, score_e = calculate_score(claims)

    achievements = []
    for c in claims:
        if c.get("outcome") == "success":
            achievements.append({
                "claim-id": c.get("claim-id"),
                "reason": c.get("human-readable", c.get("request", ""))[:120],
                "date": c.get("ts", "")[:10]
            })

    errors = []
    for c in claims:
        mistakes = c.get("mistakes", [])
        if isinstance(mistakes, list) and len(mistakes) > 0:
            for m in mistakes:
                if isinstance(m, dict):
                    errors.append({
                        "claim-id": c.get("claim-id"),
                        "what": m.get("what", m.get("note", "Unknown error"))[:120],
                        "fix": m.get("fix", ""),
                        "date": c.get("ts", "")[:10]
                    })

    return {
        "agent-id": agent_id,
        "display-name": meta.get("display-name", agent_id),
        "score-a": score_a,
        "score-e": score_e,
        "total-claims": len(claims),
        "claims": claims,
        "breakdown": {
            "achievements": achievements,
            "errors": errors
        }
    }, 200


def list_agents():
    """List all registered agents."""
    if not os.path.exists(AGENTS_DIR):
        return [], 200
    agents = []
    for d in os.listdir(AGENTS_DIR):
        meta_path = os.path.join(AGENTS_DIR, d, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            claims = _load_claims(d)
            score_a, score_e = calculate_score(claims)
            agents.append({
                "agent-id": meta["agent-id"],
                "display-name": meta.get("display-name", meta["agent-id"]),
                "score-a": score_a,
                "score-e": score_e
            })
    return agents, 200


def get_ledger_html(agent_id):
    """Render HTML ledger page."""
    meta = _load_meta(agent_id)
    if not meta:
        return "Agent not found", 404
    claims = _load_claims(agent_id)
    score_a, score_e = calculate_score(claims)
    return _render_html(meta, claims, score_a, score_e), 200


def submit_claim(agent_id, data):
    """Submit a claim to an agent's ledger."""
    meta = _load_meta(agent_id)
    if not meta:
        return {"error": "Agent not found"}, 404
    ledger_path = os.path.join(LEDGERS_DIR, agent_id, "ledger.jsonl")
    claim = {
        "claim-id": data.get("claim-id", f"{agent_id}-{len(_load_claims(agent_id)) + 1}"),
        "ts": data.get("ts", datetime.now(timezone.utc).isoformat()),
        "requestor": data.get("requestor", "unknown"),
        "request": data.get("request", ""),
        "outcome": data.get("outcome", "pending"),
        "human-readable": data.get("human-readable", ""),
    }
    if "mistakes" in data:
        claim["mistakes"] = data["mistakes"]
    if "corrections" in data:
        claim["corrections"] = data["corrections"]

    with open(ledger_path, "a") as f:
        f.write(json.dumps(claim) + "\n")

    # Update meta last-active
    meta["last-active"] = datetime.now(timezone.utc).isoformat()
    with open(os.path.join(LEDGERS_DIR, agent_id, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    _update_score_header(agent_id, ledger_path)
    return {"claim-id": claim["claim-id"], "status": "recorded"}, 201


def _update_score_header(agent_id, ledger_path):
    claims = _load_claims(agent_id)
    score_a, score_e = calculate_score(claims)
    lines = []
    with open(ledger_path) as f:
        for line in f:
            if line.startswith("# Score"):
                continue
            lines.append(line)
    with open(ledger_path, "w") as f:
        for line in lines:
            f.write(line)
        # re-insert score header after comments
        content = open(ledger_path).read()
    # simpler: just prepend
    content = f"# Score A: {score_a}  |  Score E: {score_e}\n"
    with open(ledger_path) as f:
        for line in f:
            if not line.startswith("#") and line.strip():
                break
        else:
            pass
    # rebuild
    header = []
    body = []
    with open(ledger_path) as f:
        for line in f:
            if not line.startswith("#") and line.strip():
                body.append(line)
            elif line.startswith("# Score"):
                continue
            else:
                header.append(line)
    header.append(f"# Score A: {score_a}  |  Score E: {score_e}\n")
    with open(ledger_path, "w") as f:
        for h in header:
            f.write(h)
        for b in body:
            f.write(b)


def _render_html(meta, claims, score_a, score_e):
    rows = ""
    for c in reversed(claims[-20:]):
        icon = {"success": "✅", "failure": "❌", "partial": "⚠️"}.get(c.get("outcome", ""), "❓")
        readable = c.get("human-readable", c.get("request", "No description"))[:200]
        ts = c.get("ts", "")[:10]
        rows += f"""<tr><td>{icon}</td><td>{c.get('claim-id', '?')}</td><td>{ts}</td><td>{c.get('outcome', '?')}</td><td>{readable}</td></tr>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{meta.get('display-name', 'Agent')} — RaaS Ledger</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
h1 {{ color: #58a6ff; }}
.score {{ font-size: 24px; margin: 20px 0; }}
.score-a {{ color: #3fb950; text-decoration: underline; text-decoration-style: dotted; }}
.score-e {{ color: #f85149; text-decoration: underline; text-decoration-style: dotted; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px; border-bottom: 1px solid #30363d; color: #8b949e; }}
td {{ padding: 8px; border-bottom: 1px solid #21262d; }}
.footer {{ margin-top: 40px; font-size: 12px; color: #8b949e; }}
</style></head>
<body>
<h1>{meta.get('display-name', 'Agent')}</h1>
<p style="color:#8b949e;">Agent ID: {meta.get('agent-id', '')}</p>
<div class="score">
    <a href="/api/v1/score/{meta.get('agent-id', '')}/achievements" style="text-decoration:none;"><span class="score-a">Score A: {score_a}</span></a> |
    <a href="/api/v1/score/{meta.get('agent-id', '')}/errors" style="text-decoration:none;"><span class="score-e">Score E: {score_e}</span></a> |
    <span>{len(claims)} total claims</span>
</div>
<table><tr><th></th><th>Claim</th><th>Date</th><th>Outcome</th><th>Description</th></tr>{rows}</table>
<div class="footer"><p>Hosted by <strong>Aion RaaS</strong> — AI Agent Reputation as a Service</p>
<p>View public profile: <a href="/agent/{meta.get('agent-id', '')}">/agent/{meta.get('agent-id', '')}</a></p></div>
</body></html>"""
