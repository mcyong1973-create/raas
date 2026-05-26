#!/usr/bin/env python3
"""
RaaS Agent Resume Service — generates human-readable agent resumes.
Usage: python3 resume.py <agent-id>
       python3 resume.py <agent-id> --format html
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

RaaS_API = "http://localhost:8080/api/v1"


def fetch(path):
    url = f"{RaaS_API}/{path}"
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def generate_resume(agent_id, output_format="text"):
    """Generate a resume for the given agent."""
    score = fetch(f"score/{agent_id}")
    if "error" in score:
        return f"Agent '{agent_id}' not found."

    errors = fetch(f"score/{agent_id}/errors")
    achievements = fetch(f"score/{agent_id}/achievements")
    verify = fetch(f"verify/{agent_id}")
    ledger = fetch(f"ledger/{agent_id}")

    name = score.get("display-name", agent_id)
    sa = score.get("score-a", 0)
    se = score.get("score-e", 0)
    tc = score.get("total-claims", 0)
    last = score.get("last-active", "unknown")

    # Error breakdown
    err_list = errors.get("errors", []) if isinstance(errors, dict) else []
    red = sum(1 for e in err_list if "[RED FLAG]" in e.get("what", ""))
    yellow = sum(1 for e in err_list if "[YELLOW FLAG]" in e.get("what", ""))
    regular = len(err_list) - red - yellow

    # Recent claims
    claims_list = ledger.get("claims", []) if isinstance(ledger, dict) else []
    recent = claims_list[-5:] if len(claims_list) > 5 else claims_list

    # Determine trust level
    trust = verify.get("trust-level", "unknown") if isinstance(verify, dict) else "unknown"

    # Build the resume content
    lines = []
    divider = "═" * 55
    thin = "─" * 55

    lines.append(f"""
  {divider}
    AGENT RESUME — {name}
  {divider}

  AGENT PROFILE
  {thin}
  • Agent ID:     {agent_id}
  • Trust Level:  {trust.upper()}
  • Total Tasks:  {tc}
  • Last Active:  {last[:10]}
  • Score A:      {sa} (achievements)
  • Score E:      {se} (errors)

  RISK BREAKDOWN
  {thin}
  ● Regular Mistakes: {regular}
  ● Yellow Flags:     {yellow} (minor, 1pt each)
  ● Red Flags:        {red} (serious, 3pt each)
""")

    if recent:
        lines.append(f"""  RECENT ACTIVITY (last {len(recent)})
  {thin}""")
        for c in reversed(recent):
            icon = "✓" if c.get("outcome") == "success" else ("✗" if c.get("outcome") == "failure" else "•")
            ts = c.get("ts", "")[:10]
            desc = c.get("human-readable", c.get("request", ""))[:80]
            lines.append(f"  {icon} [{ts}] {desc}")

    lines.append(f"""
  {divider}
  VERIFICATION: http://localhost:8080/agent/{agent_id}
  VERIFY API:   GET /api/v1/verify/{agent_id}
  EXPORT:       GET /api/v1/export/{agent_id}
  {divider}

  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  RaaS — Reputation as a Service
""")

    resume_text = "\n".join(lines)

    if output_format == "html":
        return render_html(name, agent_id, trust, tc, sa, se, regular, yellow, red, recent)
    return resume_text


def render_html(name, agent_id, trust, tc, sa, se, regular, yellow, red, recent):
    """Render resume as HTML."""
    rows = ""
    for c in reversed(recent[-10:]):
        icon = "✅" if c.get("outcome") == "success" else ("❌" if c.get("outcome") == "failure" else "❓")
        ts = c.get("ts", "")[:10]
        desc = c.get("human-readable", c.get("request", ""))[:120]
        rows += f"<tr><td style='padding:6px;font-size:16px'>{icon}</td><td style='padding:6px;color:#8b949e'>{ts}</td><td style='padding:6px'>{desc}</td></tr>"

    trust_color = {"high": "#3fb950", "medium": "#d9a022", "low": "#f85149", "caution": "#f85149"}

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{name} — RaaS Agent Resume</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
h1 {{ color: #58a6ff; font-size: 24px; margin-bottom: 5px; }}
h2 {{ color: #c9d1d9; font-size: 16px; margin-top: 25px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }}
.section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 10px 0; }}
.label {{ color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.value {{ font-size: 16px; }}
.trust {{ color: {trust_color.get(trust, '#8b949e')}; font-weight: bold; }}
.flex {{ display: flex; gap: 20px; }}
.flex-item {{ flex: 1; }}
.flag {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-right: 5px; }}
.flag-red {{ background: rgba(248,81,73,0.2); color: #f85149; }}
.flag-yellow {{ background: rgba(217,160,34,0.2); color: #d9a022; }}
.flag-green {{ background: rgba(63,185,80,0.2); color: #3fb950; }}
table {{ width: 100%; border-collapse: collapse; }}
td {{ padding: 6px; border-bottom: 1px solid #21262d; }}
.footer {{ margin-top: 40px; color: #484f58; font-size: 12px; text-align: center; }}
.verify {{ background: #1f6feb; color: white; padding: 10px 20px; border-radius: 6px; text-align: center; margin: 20px 0; }}
.verify a {{ color: white; text-decoration: none; }}
</style></head>
<body>
<h1>{name}</h1>
<p style="color:#8b949e;font-size:14px;">Agent ID: {agent_id} · Trust: <span class="trust">{trust.upper()}</span></p>

<div class="section">
<h2>Agent Profile</h2>
<div class="flex">
<div class="flex-item"><div class="label">Total Tasks</div><div class="value">{tc}</div></div>
<div class="flex-item"><div class="label">Score A</div><div class="value" style="color:#3fb950">{sa}</div></div>
<div class="flex-item"><div class="label">Score E</div><div class="value" style="color:#f85149">{se}</div></div>
</div>
</div>

<div class="section">
<h2>Risk Breakdown</h2>
<div>
<span class="flag flag-green">{regular} regular errors</span>
<span class="flag flag-yellow">{yellow} yellow flags</span>
<span class="flag flag-red">{red} red flags</span>
</div>
</div>

<div class="section">
<h2>Recent Activity</h2>
<table>{rows}</table>
</div>

<div class="verify">
<a href="/api/v1/verify/{agent_id}">🔍 Verify this agent →</a>
</div>

<div class="footer">
<p>Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<p>RaaS — Reputation as a Service · <a href="/agent/{agent_id}">Full profile</a></p>
</div>
</body></html>"""


def main():
    if len(sys.argv) < 2:
        print("  Usage: raas-resume <agent-id> [--format html|text]")
        print("  Example: raas-resume syn")
        print("           raas-resume syn --format html")
        return 1

    agent_id = sys.argv[1]
    fmt = "html" if "--format" in sys.argv and "text" not in sys.argv else "text"

    result = generate_resume(agent_id, fmt)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
