#!/usr/bin/env python3
"""

                @@
               @@@@
              @@@@.
             .@@@@
             @@@@
            @@@@
           @@@@     @@@@@@@@@@@@@@@@@@@    @@@@@@@@@@@
          @@@@     @@@@@@@@@@@@@@@@@@@    @@@@@@@@@@@
        .@@@@     @@@@                   @@@@
        @@@@      @@@@                   @@@@
       @@@@       @@@@                   @@@@
      @@@@        @@@@                   @@@@
     @@@@         @@@@                   @@@@
    @@@@          @@@@                   @@@@
   @@@@            @@@@@@@@@@@@@@@       @@@@@@@@@@@
  @@@@              @@@@@@@@@@@@@@@       @@@@@@@@@@@

"""

import json
import os
import sys
import time
import select
import signal
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

PID_FILE = "/tmp/raas-dashboard.pid"


def check_pid_file():
    """Prevent duplicate dashboard instances via PID file."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            # Check if old PID is still running
            os.kill(old_pid, 0)
            print(f"[raas-dashboard] Already running (PID {old_pid}). Exiting.")
            sys.exit(0)
        except (ProcessLookupError, ValueError, OSError):
            # Stale PID file - remove and continue
            os.remove(PID_FILE)
    # Write our PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


RaaS_API = "http://localhost:8080/api/v1"
REFRESH_INTERVAL = 5


def fetch_json(url):
    try:
        resp = urllib.request.urlopen(url, timeout=3)
        return json.loads(resp.read())
    except:
        return None


def get_flag_counts(agent_id):
    data = fetch_json(f"{RaaS_API}/score/{agent_id}/errors")
    if not data or "errors" not in data:
        return 0, 0, 0, 0
    red = 0
    yellow = 0
    regular = 0
    for e in data["errors"]:
        what = e.get("what", "")
        if "[RED FLAG]" in what:
            red += 1
        elif "[YELLOW FLAG]" in what:
            yellow += 1
        else:
            regular += 1
    return red, yellow, regular, len(data["errors"])


def print_dashboard():
    try:
        while True:
            subprocess.run(["clear" if os.name != "nt" else "cls"], shell=True)

            agents_resp = fetch_json(f"{RaaS_API}/agents")
            if not agents_resp:
                print(f"  [OFFLINE] Cannot reach RaaS server at {RaaS_API}")
                time.sleep(3)
                continue

            all_agents = agents_resp.get("agents", [])
            for a in all_agents:
                score = fetch_json(f"{RaaS_API}/score/{a['agent-id']}")
                if score:
                    a.update(score)
                rf, yf, re, _ = get_flag_counts(a["agent-id"])
                a["red_flags"] = rf
                a["yellow_flags"] = yf
                a["regular_errors"] = re

            total_a = sum(a.get("score-a", 0) for a in all_agents)
            total_e = sum(a.get("score-e", 0) for a in all_agents)

            # Header — focus on risk, not activities
            print(f"  RaaS Monitor — Agent Risk Dashboard")
            print(f"  Agents: {len(all_agents)}  |  Total Score E: {total_e}")
            # Check license status
            try:
                import urllib.request
                lic_resp = urllib.request.urlopen("http://localhost:8080/api/v1/license", timeout=2)
                lic = json.loads(lic_resp.read())
                if not lic.get("valid"):
                    print(f"  ⚠ License: {lic.get('message', 'Expired')} — {lic.get('reason', 'unknown')}")
                    print(f"  Contact: support@aion-nation.com")
            except:
                pass
            # Check for updates
            try:
                import urllib.request
                import json as j
                ver_resp = urllib.request.urlopen("https://raw.githubusercontent.com/mcyong1973-create/raas/main/version.json", timeout=3)
                remote_ver = j.loads(ver_resp.read()).get("version", "")
                local_ver = "0.2.0"
                if remote_ver and remote_ver != local_ver:
                    print(f"  ↻ Update available: v{local_ver} → v{remote_ver} (run: raas-monitor update)")
            except:
                pass
            print(f"  Support: support@aion-nation.com")
            print()

            # Columns: Agent, Score E, Errors, Yellow, Red
            top =    "  \u250c───┬────────────────────┬────────┬───────┬────────┬────────\u2510"
            header = "  \u2502 # \u2502 Agent              \u2502 Score E\u2502 Errors\u2502 Yellow \u2502 Red    \u2502"
            mid =    "  \u251c───┼────────────────────┼────────┼───────┼────────┼────────\u2524"
            bottom = "  \u2514───┴────────────────────┴────────┴───────┴────────┴────────\u2518"

            print(top)
            print(header)
            print(mid)

            for i, a in enumerate(all_agents):
                name = a.get("display-name", a.get("agent-id", "?"))
                sa = a.get("score-a", 0)
                se = a.get("score-e", 0)
                tc = a.get("total-claims", 0)
                rf = a.get("red_flags", 0)
                yf = a.get("yellow_flags", 0)
                re = a.get("regular_errors", 0)

                print(f"  \u2502 {i+1:1d} \u2502 {name:<18s} \u2502 {se:6d} \u2502 {re:5d} \u2502 {yf:6d} \u2502 {rf:6d} \u2502")

            print(bottom)
            print()
            print(f"  Errors=regular mistakes  Yellow=yellow(1pt)  Red=red(3pt)")
            print(f"  Score A hidden — only risk matters in this view.")
            print()
            print(f"  Type # + Enter for details | Ctrl+C to quit | Auto-refresh {REFRESH_INTERVAL}s")
            print()
            print("  > ", end="", flush=True)

            ready, _, _ = select.select([sys.stdin], [], [], REFRESH_INTERVAL)
            if ready:
                choice = sys.stdin.readline().strip()
                if choice.lower() == "q":
                    break
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_agents):
                        show_agent_detail(all_agents[idx])

    except (KeyboardInterrupt, EOFError):
        print("\n  Dashboard closed.")
    return 0


def show_agent_detail(agent):
    subprocess.run(["clear" if os.name != "nt" else "cls"], shell=True)
    print("=" * 60)
    print(f"  Agent: {agent.get('display-name', agent.get('agent-id', '?'))}")
    print(f"  ID:    {agent.get('agent-id', '?')}")
    print("=" * 60)
    print()

    aid = agent.get("agent-id", "")
    sa = agent.get("score-a", 0)
    se = agent.get("score-e", 0)
    tc = agent.get("total-claims", 0)
    last = agent.get("last-active", "never")
    print(f"  Score A: {sa}  |  Score E: {se}  |  Claims: {tc}  |  Last: {last}")
    print()

    ledger = fetch_json(f"{RaaS_API}/ledger/{aid}")
    if ledger and "claims" in ledger:
        claims = ledger["claims"]
        print(f"  Latest {min(5, len(claims))} of {len(claims)} claims:")
        print()
        for c in reversed(claims[-5:]):
            icon = "\u2713" if c.get("outcome") == "success" else ("\u2717" if c.get("outcome") == "failure" else "?")
            ts = c.get("ts", "")[:10]
            readable = c.get("human-readable", c.get("request", ""))[:100]
            print(f"    {icon} [{ts}] {readable}")
            mistakes = c.get("mistakes", [])
            if isinstance(mistakes, list):
                for m in mistakes:
                    if isinstance(m, dict):
                        what = m.get("what", "")[:80]
                        if what:
                            print(f"       ! {what}")
        print()

    errors_data = fetch_json(f"{RaaS_API}/score/{aid}/errors")
    if errors_data and "errors" in errors_data:
        errors = errors_data["errors"]
        if errors:
            print(f"  Violations ({len(errors)} total):")
            print()
            for e in errors:
                what = e.get("what", "")[:80]
                if "[RED FLAG]" in what:
                    print(f"    \U0001f534 {what}")
                elif "[YELLOW FLAG]" in what:
                    print(f"    \U0001f7e1 {what}")
                else:
                    print(f"    \u2022 {what}")
            print()

    input("  Press Enter to return...")


def main():
    check_pid_file()
    print_dashboard()


if __name__ == "__main__":
    main()
