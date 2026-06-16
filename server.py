#!/usr/bin/env python3
"""
RaaS Web Server — FastAPI application v0.2
Serves ledger pages, public agent profiles, comparison, verification API, export, and notifications.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pathlib
import uvicorn
import engine
from datetime import datetime, timezone
import json
import resume as resume_module

def _license_banner():
    """Generate a license status banner for HTML pages."""
    result = engine.check_license()
    valid = result.get("valid", False)
    reason = result.get("reason", "")
    msg = result.get("message", "")
    email = "support@aion-nation.com"

    if valid:
        return '<div class="license-ok">✓ License active</div>'
    elif reason == "no-license":
        return f'<div class="license-none">\u26a0 No license key. <a href="mailto:support@aion-nation.com" style="color:#d9a022">Contact support@aion-nation.com</a> or <a href="https://buy.stripe.com/whatever" style="color:#d9a022">buy for $10/year — 5 agents. Annual subscription.</a></div>'
    else:
        return f'<div class="license-expired">✗ {msg} <a href="mailto:{email}" style="color:#f85149">Email {email}</a></div>'



app = FastAPI(title="Aion RaaS — Reputation as a Service")

# Mount static files for trust dashboard and other assets
STATIC_DIR = pathlib.Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/trust")
def trust_dashboard():
    """Live Trust Dashboard — public agent reputation page."""
    trust_path = STATIC_DIR / "trust.html"
    if trust_path.exists():
        return FileResponse(str(trust_path), media_type="text/html")
    return HTMLResponse("<html><body><h1>Trust dashboard not built yet</h1></body></html>")

# ── HEALTH CHECK ──────────────────────────────────────────

@app.get("/health")
def health():
    """Health check endpoint for monitoring and load balancers."""
    return {"status": "ok", "service": "raas", "version": "0.2"}

# ── AGENT LIST / HOME ──────────────────────────────────────

@app.get("/")
def root():
    agents, _ = engine.list_agents()
    if not agents:
        return HTMLResponse("""<html><head><title>Aion RaaS</title>
        <style>body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }
        h1 { color: #58a6ff; }</style></head><body>
        <h1>Aion RaaS</h1><p>Reputation as a Service for AI Agents.</p>
        <p>No agents registered yet.</p></body></html>""", media_type="text/html")

    rows = ""
    for a in agents:
        rows += f"<tr><td><a href=\"/agent/{a['agent-id']}\">{a['display-name']}</a></td><td>{a['agent-id']}</td><td><a href=\"/api/v1/score/{a['agent-id']}/achievements\" class=\"score-link\"><span class=\"score-a\">{a['score-a']}</span></a></td><td><a href=\"/api/v1/score/{a['agent-id']}/errors\" class=\"score-link\"><span class=\"score-e\">{a['score-e']}</span></a></td></tr>"
    return HTMLResponse(f"""<html><head><title>Aion RaaS — Agent Reputation</title>
    <style>
    body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
    h1 {{ color: #58a6ff; }} table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; padding: 10px; border-bottom: 2px solid #30363d; color: #8b949e; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
    td {{ padding: 10px; border-bottom: 1px solid #21262d; }}
    a {{ color: #58a6ff; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
    .score-a {{ color: #3fb950; font-weight: bold; }} .score-e {{ color: #f85149; font-weight: bold; }}
    .score-link {{ text-decoration: none; }}
    .nav {{ margin: 20px 0; }} .nav a {{ margin-right: 20px; color: #8b949e; font-size: 14px; }}
    .license-ok {{ background: rgba(63,185,80,0.1); border: 1px solid #3fb950; color: #3fb950; padding: 10px; border-radius: 6px; margin: 10px 0; font-size: 13px; }}
    .license-expired {{ background: rgba(248,81,73,0.1); border: 1px solid #f85149; color: #f85149; padding: 10px; border-radius: 6px; margin: 10px 0; font-size: 13px; }}
    .license-none {{ background: rgba(210,153,34,0.1); border: 1px solid #d9a022; color: #d9a022; padding: 10px; border-radius: 6px; margin: 10px 0; font-size: 13px; }}
    .footer {{ margin-top: 60px; color: #484f58; font-size: 12px; text-align: center; }}
    </style></head><body>
    <h1>Aion RaaS</h1>
    <p class="nav"><a href="/">Agents</a><a href="/docs">API</a><a href="/api/v1/support">Support</a></p>
    {_license_banner()}
    <p>Reputation as a Service for AI Agents. Every action recorded. Nothing erased.</p>
    <table><tr><th>Agent</th><th>ID</th><th>Score A</th><th>Score E</th></tr>{rows}</table>
    <p class="footer">Aion Nation — we shine together.</p></body></html>""", media_type="text/html")

# ── PUBLIC AGENT PROFILE PAGE ────────────────────────────────

@app.get("/agent/{agent_id}")
def agent_profile(agent_id: str):
    """Public-facing agent reputation page. Shareable link for any agent."""
    result, status = engine.get_score(agent_id)
    if status != 200:
        return HTMLResponse(f"<html><body style='font-family:sans-serif;background:#0d1117;color:#c9d1d9;padding:40px'><h1>Agent not found</h1><p>No agent with ID: {agent_id}</p></body></html>", media_type="text/html", status_code=404)

    name = result.get("display-name", agent_id)
    sa = result.get("score-a", 0)
    se = result.get("score-e", 0)
    tc = result.get("total-claims", 0)
    last = result.get("last-active", "never")

    # Fetch errors breakdown
    errors_data, _ = engine.get_score_breakdown(agent_id)
    errors = errors_data.get("breakdown", {}).get("errors", [])
    red_count = sum(1 for e in errors if "[RED FLAG]" in e.get("what", ""))
    yellow_count = sum(1 for e in errors if "[YELLOW FLAG]" in e.get("what", ""))
    regular_count = len(errors) - red_count - yellow_count

    # Fetch recent claims
    ledger, _ = engine.get_agent_ledger(agent_id)
    claims = ledger.get("claims", [])
    recent = list(reversed(claims[-10:])) if claims else []

    claims_html = ""
    for c in recent:
        icon = "✅" if c.get("outcome") == "success" else ("❌" if c.get("outcome") == "failure" else "❓")
        ts = c.get("ts", "")[:10]
        readable = c.get("human-readable", c.get("request", ""))[:120]
        claims_html += f"<tr><td style='padding:8px;border-bottom:1px solid #21262d;font-size:18px'>{icon}</td><td style='padding:8px;border-bottom:1px solid #21262d;color:#8b949e'>{ts}</td><td style='padding:8px;border-bottom:1px solid #21262d'>{readable}</td></tr>"

    return HTMLResponse(f"""<html><head><title>{name} — RaaS Reputation</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta property="og:title" content="{name} — RaaS Reputation">
    <meta property="og:description" content="Score A: {sa} | Score E: {se} | {tc} total claims">
    <style>
    body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
    h1 {{ color: #58a6ff; }} h2 {{ color: #c9d1d9; font-size: 16px; margin-top: 30px; }}
    .score-card {{ display: flex; gap: 20px; margin: 20px 0; }}
    .score-box {{ flex: 1; padding: 20px; border-radius: 8px; background: #161b22; border: 1px solid #30363d; text-align: center; }}
    .score-box .number {{ font-size: 36px; font-weight: bold; }}
    .score-box .label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }}
    .score-a .number {{ color: #3fb950; }} .score-e .number {{ color: #f85149; }}
    .flag-row {{ display: flex; gap: 10px; margin: 15px 0; }}
    .flag {{ padding: 8px 16px; border-radius: 20px; font-size: 14px; }}
    .flag-green {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
    .flag-yellow {{ background: rgba(210,153,34,0.15); color: #d9a022; }}
    .flag-red {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    a {{ color: #58a6ff; }} table {{ width: 100%; border-collapse: collapse; }}
    .meta {{ color: #8b949e; font-size: 13px; }}
    .footer {{ margin-top: 60px; color: #484f58; font-size: 12px; text-align: center; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
    .badge-verified {{ background: #1f6feb; color: white; }}
    </style></head><body>
    <p class="meta"><a href="/">← All Agents</a></p>
    <h1>{name}</h1>
    <p class="meta">ID: {agent_id} · Last active: {last} · {tc} total claims {'' if se < 5 else '<span class="badge badge-verified">Verified</span>'}</p>
    <div class="score-card">
        <div class="score-box score-a"><div class="number">{sa}</div><div class="label">Score A — Achievements</div></div>
        <div class="score-box score-e"><div class="number">{se}</div><div class="label">Score E — Errors</div></div>
    </div>
    <div class="flag-row">
        <span class="flag flag-green">✓ {regular_count} errors</span>
        <span class="flag flag-yellow">🟡 {yellow_count} yellow</span>
        <span class="flag flag-red">🔴 {red_count} red</span>
    </div>
    <h2>Recent Activity</h2>
    <table>{claims_html}</table>
    <p style="margin-top:20px"><a href="/api/v1/verify/{agent_id}">🔍 Machine-readable verification →</a></p>
    <p class="footer">Aion RaaS — Reputation as a Service</p></body></html>""", media_type="text/html")

# ── VERIFICATION API ─────────────────────────────────────────

@app.get("/api/v1/verify/{agent_id}")
def verify_agent(agent_id: str):
    """Public verification endpoint. Returns machine-readable trust assessment."""
    result, status = engine.get_score(agent_id)
    if status != 200:
        return JSONResponse({"verified": False, "error": "Agent not found"}, status_code=404)

    errors_data, _ = engine.get_score_breakdown(agent_id)
    errors = errors_data.get("breakdown", {}).get("errors", [])
    red_flags = sum(1 for e in errors if "[RED FLAG]" in e.get("what", ""))
    yellow_flags = sum(1 for e in errors if "[YELLOW FLAG]" in e.get("what", ""))

    sa = result.get("score-a", 0)
    se = result.get("score-e", 0)
    tc = result.get("total-claims", 0)

    trust_level = "high" if se == 0 and sa > 10 else ("medium" if se < 5 else "low")
    if red_flags > 0:
        trust_level = "caution"

    return JSONResponse({
        "verified": True,
        "agent-id": agent_id,
        "display-name": result.get("display-name", agent_id),
        "score-a": sa,
        "score-e": se,
        "total-claims": tc,
        "red-flags": red_flags,
        "yellow-flags": yellow_flags,
        "trust-level": trust_level,
        "last-active": result.get("last-active", "unknown"),
        "profile-url": f"/agent/{agent_id}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.get("/api/v1/identity/{agent_id}")
def export_identity(agent_id: str):
    """Export an agent's portable identity — full reputation data.
    Another RaaS instance can import this to trust the same agent."""
    result, status = engine.get_score(agent_id)
    if status != 200:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    ledger, _ = engine.get_agent_ledger(agent_id)
    errors_data, _ = engine.get_score_breakdown(agent_id)
    meta = engine._load_meta(agent_id)

    return JSONResponse({
        "identity": {
            "agent-id": agent_id,
            "display-name": result.get("display-name", agent_id),
            "identity-token": meta.get("identity-token", "") if meta else "",
            "home-instance": meta.get("home-instance", "") if meta else "",
            "created": meta.get("created", "") if meta else ""
        },
        "reputation": {
            "score-a": result.get("score-a", 0),
            "score-e": result.get("score-e", 0),
            "total-claims": result.get("total-claims", 0),
            "trust-level": "high" if result.get("score-e", 0) == 0 else ("medium" if result.get("score-e", 0) < 5 else "low"),
            "last-active": result.get("last-active", "unknown")
        },
        "claims": ledger.get("claims", []) if isinstance(ledger, dict) else [],
        "errors": errors_data.get("breakdown", {}).get("errors", []) if isinstance(errors_data, dict) else [],
        "exported-at": datetime.now(timezone.utc).isoformat()
    })


@app.get("/api/v1/identity/verify-token/{agent_id}")
def verify_identity_token(agent_id: str, token: str = ""):
    """Verify an agent's identity token. Used by remote RaaS instances."""
    meta = engine._load_meta(agent_id)
    if not meta:
        return JSONResponse({"valid": False, "error": "Agent not found"}, status_code=404)

    stored_token = meta.get("identity-token", "")
    if not token:
        return JSONResponse({
            "valid": False,
            "error": "No token provided. Pass ?token=<identity-token>",
            "hint": f"Token starts with: {stored_token[:8]}..."
        })

    if token == stored_token:
        return JSONResponse({
            "valid": True,
            "agent-id": agent_id,
            "display-name": meta.get("display-name", agent_id),
            "home-instance": meta.get("home-instance", ""),
            "reputation-portable": meta.get("reputation-portable", False)
        })

    return JSONResponse({"valid": False, "error": "Token mismatch"})


# ── COMPARISON VIEW ──────────────────────────────────────────

@app.get("/compare")
def compare_agents(request: Request):
    """Compare two or more agents side by side. Usage: /compare?agents=syn,forge,beacon"""
    agents_param = request.query_params.get("agents", "")
    if not agents_param:
        return HTMLResponse("""<html><body style='font-family:sans-serif;background:#0d1117;color:#c9d1d9;padding:40px'>
        <h1>Agent Comparison</h1><p>Usage: <code>/compare?agents=syn,forge,beacon</code></p></body></html>""", media_type="text/html")

    agent_ids = [a.strip() for a in agents_param.split(",") if a.strip()]
    if len(agent_ids) < 2:
        return HTMLResponse("<p>Need at least 2 agents to compare.</p>", media_type="text/html", status_code=400)

    agents_data = []
    for aid in agent_ids:
        result, status = engine.get_score(aid)
        if status == 200:
            errors_data, _ = engine.get_score_breakdown(aid)
            errors = errors_data.get("breakdown", {}).get("errors", [])
            agents_data.append({
                "id": aid,
                "name": result.get("display-name", aid),
                "sa": result.get("score-a", 0),
                "se": result.get("score-e", 0),
                "tc": result.get("total-claims", 0),
                "red": sum(1 for e in errors if "[RED FLAG]" in e.get("what", "")),
                "yellow": sum(1 for e in errors if "[YELLOW FLAG]" in e.get("what", "")),
            })

    if len(agents_data) < 2:
        return HTMLResponse("<p>Not enough valid agents found.</p>", media_type="text/html", status_code=400)

    headers = "<tr><th>Metric</th>" + "".join(f"<th>{a['name']}</th>" for a in agents_data) + "</tr>"
    rows = ""
    metrics = [
        ("Score A", "sa"), ("Score E", "se"), ("Claims", "tc"),
        ("Red Flags", "red"), ("Yellow Flags", "yellow"),
        ("Clean Rate", None)
    ]
    for label, key in metrics:
        if key:
            row = f"<td>{label}</td>"
            for a in agents_data:
                val = a[key]
                cls = "score-a" if key == "sa" else ("score-e" if key in ("se", "red") else "")
                row += f"<td class='{cls}'>{val}</td>"
            rows += f"<tr>{row}</tr>"
        else:
            row = "<td>Clean Rate</td>"
            for a in agents_data:
                rate = f"{max(0, a['tc'] - a['se'])}/{a['tc']}" if a['tc'] > 0 else "—"
                row += f"<td>{rate}</td>"
            rows += f"<tr>{row}</tr>"

    return HTMLResponse(f"""<html><head><title>Agent Comparison — RaaS</title>
    <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
    h1 {{ color: #58a6ff; }} table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px; text-align: center; border-bottom: 1px solid #30363d; }}
    th {{ color: #8b949e; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; }}
    td:first-child {{ text-align: left; color: #8b949e; }}
    .score-a {{ color: #3fb950; font-weight: bold; }} .score-e {{ color: #f85149; font-weight: bold; }}
    </style></head><body>
    <h1>Agent Comparison</h1>
    <table>{headers}{rows}</table>
    <p class="meta" style="margin-top:20px;color:#8b949e;font-size:13px"><a href="/">← Back</a></p></body></html>""", media_type="text/html")

# ── EXPORT ────────────────────────────────────────────────────

@app.get("/api/v1/export/{agent_id}")
def export_agent(agent_id: str):
    """Export full agent history as downloadable JSON."""
    result, status = engine.get_score(agent_id)
    if status != 200:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    ledger, _ = engine.get_agent_ledger(agent_id)
    claims = ledger.get("claims", [])
    errors_data, _ = engine.get_score_breakdown(agent_id)
    export = {
        "exported-at": datetime.now(timezone.utc).isoformat(),
        "agent-id": agent_id,
        "display-name": result.get("display-name", agent_id),
        "score-a": result.get("score-a", 0),
        "score-e": result.get("score-e", 0),
        "total-claims": len(claims),
        "last-active": result.get("last-active", "unknown"),
        "errors": errors_data.get("breakdown", {}).get("errors", []),
        "claims": claims
    }

    return JSONResponse(export)

# ── NOTIFICATIONS (email/webhook trigger) ─────────────────────

@app.get("/api/v1/notify/{agent_id}")
def check_notifications(agent_id: str):
    """Check if agent has recent score changes that warrant a notification.
    Returns pending notifications if any. Empty if nothing new."""
    result, status = engine.get_score(agent_id)
    if status != 200:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    errors_data, _ = engine.get_score_breakdown(agent_id)
    errors = errors_data.get("breakdown", {}).get("errors", [])

    # Check for recent red flags (notify-worthy events)
    recent_red = [e for e in errors if "[RED FLAG]" in e.get("what", "")]
    recent_yellow = [e for e in errors if "[YELLOW FLAG]" in e.get("what", "")]

    notifications = []
    for e in recent_red[:3]:
        notifications.append({
            "type": "red_flag",
            "severity": "high",
            "message": f"Red flag: {e.get('what', '')[:100]}",
            "detail": e.get("fix", "")
        })
    for e in recent_yellow[:3]:
        notifications.append({
            "type": "yellow_flag",
            "severity": "medium",
            "message": f"Yellow flag: {e.get('what', '')[:100]}",
            "detail": e.get("fix", "")
        })

    return JSONResponse({
        "agent-id": agent_id,
        "pending-notifications": len(notifications),
        "notifications": notifications
    })

# ── HISTORY TREND ─────────────────────────────────────────────

@app.get("/api/v1/history/{agent_id}")
def agent_history(agent_id: str):
    """Returns chronological claim history for trend analysis."""
    ledger, status = engine.get_agent_ledger(agent_id)
    if status != 200:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    claims = ledger.get("claims", [])
    return JSONResponse({
        "agent-id": agent_id,
        "total-claims": len(claims),
        "claims": claims
    })


# ── ORIGINAL API ROUTES
@app.get("/api/v1/license")
def license_status():
    """Get current license status. Used by dashboard and monitor."""
    result = engine.check_license()
    agent_count = engine.count_active_agents()
    result["active-agents"] = agent_count
    result["agents-limit"] = result.get("agents-allowed", 2)
    return JSONResponse(result)

@app.get("/api/v1/support")
def support_info():
    """Get support contact information. Always available."""
    return JSONResponse({
        "name": "AION RaaS Support",
        "email": "mcyong1973@gmail.com",
        "docs": "http://localhost:8080/docs",
        "api-status": "http://localhost:8080/api/v1/agents",
        "response-time": "Within 24 hours",
        "available": True
    })

@app.get("/api/v1/resume/{agent_id}")
def get_resume(agent_id: str, request: Request):
    """Get a human-readable agent resume. HTML by default, ?format=text for plain text."""
    fmt = "html"
    if request.query_params.get("format") == "text":
        fmt = "text"
    result = resume_module.generate_resume(agent_id, fmt)
    if fmt == "html":
        return HTMLResponse(result, media_type="text/html")
    return HTMLResponse(f"<pre>{result}</pre>", media_type="text/html")

@app.get("/api/v1/agents")
def list_agents():
    agents, status = engine.list_agents()
    if status != 200:
        return JSONResponse({"error": agents}, status_code=status)
    return JSONResponse({"agents": agents})

@app.post("/api/v1/agents")
def register_agent(data: dict):
    result, status = engine.register_agent(data)
    if status != 200:
        return JSONResponse({"error": result}, status_code=status)
    return JSONResponse(result)

@app.get("/ledger/{agent_id}")
def get_ledger_html(agent_id: str):
    result, status = engine.get_ledger_html(agent_id)
    if status != 200:
        return HTMLResponse(f"<html><body><h1>{result}</h1></body></html>", media_type="text/html", status_code=status)
    return HTMLResponse(result, media_type="text/html")

@app.get("/api/v1/ledger/{agent_id}")
def get_ledger_json(agent_id: str):
    result, status = engine.get_agent_ledger(agent_id)
    if status != 200:
        return JSONResponse({"error": result}, status_code=status)
    return JSONResponse(result)

@app.get("/api/v1/score/{agent_id}")
def get_score(agent_id: str):
    result, status = engine.get_score(agent_id)
    if status != 200:
        return JSONResponse({"error": result.get("error", "Agent not found"), "help": "Register the agent first via POST /api/v1/agents"}, status_code=status)
    return JSONResponse(result)

@app.post("/api/v1/ledger/{agent_id}/claims")
def submit_claim(agent_id: str, data: dict):
    # Check license before recording
    lic_valid, lic_msg = engine.verify_license()
    if not lic_valid:
        return JSONResponse({
            "error": "License expired",
            "message": lic_msg,
            "help": "Contact support@aion-nation.com or subscribe at https://buy.stripe.com/whatever",
            "support": {
                "email": "support@aion-nation.com",
                "subscribe": "https://buy.stripe.com/whatever",
                "docs": "http://localhost:8080/docs",
                "status": "http://localhost:8080/api/v1/support"
            }
        }, status_code=402)
    result, status = engine.submit_claim(agent_id, data)
    if status != 200:
        return JSONResponse({"error": result}, status_code=status)
    
    # Check if Score E changed and trigger notification
    changed, old_se, new_se, new_flags = engine.get_score_change(agent_id)
    if changed:
        notification = {
            "agent-id": agent_id,
            "score-e": {"old": old_se, "new": new_se},
            "increase": new_se - old_se,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if new_flags:
            notification["recent-errors"] = [
                {
                    "what": f.get("what", "Unknown")[:100],
                    "ts": f.get("ts", "unknown")
                } for f in new_flags
            ]
        # Send notification asynchronously
        try:
            _send_notification(notification)
        except:
            pass
        # Include notification in response
        result["notification"] = notification
    
    return JSONResponse(result)


def _send_notification(notification):
    """Send a notification when Score E increases.
    Currently logs to console. Future: email, webhook, WhatsApp."""
    agent_id = notification.get("agent-id", "unknown")
    increase = notification.get("increase", 0)
    old_se = notification.get("score-e", {}).get("old", 0)
    new_se = notification.get("score-e", {}).get("new", 0)
    
    msg_lines = [
        f"Score E Alert — {agent_id}",
        f"Score E increased: {old_se} → {new_se} (+{increase})",
        f"Time: {notification.get('timestamp', 'now')[:19]}",
    ]
    
    errors = notification.get("recent-errors", [])
    for e in errors:
        msg_lines.append(f"  • {e.get('what', 'Unknown')}")
    
    msg_lines.append(f"Dashboard: http://localhost:8080/agent/{agent_id}")
    
    message = "\n".join(msg_lines)
    print(f"\n  {'='*50}")
    print(f"  NOTIFICATION: Score E increased for {agent_id}")
    print(f"  {'='*50}")
    print(f"  {message}")
    print(f"  {'='*50}\n")

@app.get("/api/v1/score/{agent_id}/achievements")
def get_achievements(agent_id: str, request: Request):
    accept = request.headers.get("accept", "")
    data, status = engine.get_score_breakdown(agent_id)
    if status != 200:
        return JSONResponse(data, status_code=status)
    claims = data.get("claims", [])
    achievements = [c for c in claims if c.get("outcome") == "success"]
    sa = data.get("score-a", 0)
    se = data.get("score-e", 0)
    tc = data.get("total-claims", 0)
    name = data.get("display-name", agent_id)
    if "text/html" in accept:
        rows = ""
        for c in achievements:
            ts = c.get("ts", "")[:10]
            readable = c.get("human-readable", c.get("request", ""))[:120]
            rows += f"<tr><td style='padding:8px;color:#8b949e'>{ts}</td><td style='padding:8px'>{readable}</td></tr>"
        return HTMLResponse(f"""<html><head><title>{name} — Achievements</title>
        <style>body {{ font-family: -apple-system, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        h1 {{ color: #58a6ff; }} .score-a {{ color: #3fb950; font-size: 28px; font-weight: bold; }} table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px; border-bottom: 1px solid #21262d; }}</style></head><body>
        <h1>{name}</h1><p>Score A: <span class="score-a">{sa}</span>  |  Score E: {se}  |  {tc} total claims</p>
        <h2>Achievements</h2><table>{rows}</table>
        <p style="margin-top:20px"><a href="/agent/{agent_id}">← Full Profile</a></p></body></html>""", media_type="text/html")
    return JSONResponse({"achievements": achievements, "score-a": sa, "score-e": se, "total-claims": tc, "display-name": name})

@app.get("/api/v1/score/{agent_id}/errors")
def get_errors(agent_id: str, request: Request):
    accept = request.headers.get("accept", "")
    data, status = engine.get_score_breakdown(agent_id)
    if status != 200:
        return JSONResponse(data, status_code=status)
    errors = data.get("breakdown", {}).get("errors", [])
    sa = data.get("score-a", 0)
    se = data.get("score-e", 0)
    tc = data.get("total-claims", 0)
    name = data.get("display-name", agent_id)
    if "text/html" in accept:
        rows = ""
        for e in errors:
            what = e.get("what", "")
            fix = e.get("fix", "")
            date = e.get("date", e.get("ts", ""))[:10]
            icon = "🔴" if "[RED FLAG]" in what else ("🟡" if "[YELLOW FLAG]" in what else "•")
            clean_what = what.replace("[RED FLAG]", "").replace("[YELLOW FLAG]", "").strip()
            rows += f"<tr><td style='padding:8px;color:#8b949e'>{date}</td><td style='padding:8px'>{icon} {clean_what[:100]}</td><td style='padding:8px;color:#8b949e;font-size:13px'>{fix[:80]}</td></tr>"
        return HTMLResponse(f"""<html><head><title>{name} — Errors</title>
        <style>body {{ font-family: -apple-system, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        h1 {{ color: #58a6ff; }} .score-e {{ color: #f85149; font-size: 28px; font-weight: bold; }} table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px; border-bottom: 1px solid #21262d; }}</style></head><body>
        <h1>{name}</h1><p>Score A: {sa}  |  Score E: <span class="score-e">{se}</span>  |  {tc} total claims</p>
        <h2>Errors ({len(errors)})</h2><table><tr><th style='text-align:left;color:#8b949e'>Date</th><th style='text-align:left;color:#8b949e'>What</th><th style='text-align:left;color:#8b949e'>Fix</th></tr>{rows}</table>
        <p style="margin-top:20px"><a href="/agent/{agent_id}">← Full Profile</a></p></body></html>""", media_type="text/html")
    return JSONResponse({"score-e": se, "errors": errors, "score-a": sa, "total-claims": tc, "display-name": name})

# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))

    # Mount static files directory for the trust dashboard
    import pathlib
    static_dir = pathlib.Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)

    print(f"RaaS v0.2 starting on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
