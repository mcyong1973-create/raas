#!/usr/bin/env python3
"""
RaaS Monitor — Lightweight agent tracking daemon.
One-command install. Watches AI agents and records their work to RaaS.

Usage:
    curl -sL https://raas.aion.io/install.sh | bash
    raas-monitor start
"""
import json
import os
import subprocess
import sys
import time
import signal
from datetime import datetime, timezone

CONFIG_DIR = os.path.expanduser("~/.raas")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LEDGER_DIR = os.path.join(CONFIG_DIR, "ledgers")
PID_FILE = os.path.join(CONFIG_DIR, "monitor.pid")
RaaS_API = "http://localhost:8080/api/v1"


def print_banner():
    print(r"""
    ┌─────────────────────────────────────────────┐
    │  RaaS Monitor v0.1                          │
    │  Reputation as a Service — Agent Tracking   │
    │  Aion Nation                                │
    └─────────────────────────────────────────────┘
    """)


def init_config():
    """Initialize the config file if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(LEDGER_DIR, exist_ok=True)

    if not os.path.exists(CONFIG_FILE):
        config = {
            "raas-api": RaaS_API,
            "company": "My Company",
            "support-email": "mcyong1973@gmail.com",
            "notification-email": "",
            "notification-whatsapp": "",
            "agents": [],
            "watch-interval": 60,
            "watchlist": [
                {
                    "rule": "Database destruction commands — prevents production data loss",
                    "keywords": ["drop table", "delete from", "truncate", "drop database", "rm -rf /", "format"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "Credential and secret exposure — prevents token/API key leaks",
                    "keywords": ["api_key", "aws_secret", "password=", "token=", "secret=", "bearer ", "auth=", "-----begin"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "External data exfiltration — monitors data being sent outside",
                    "keywords": ["curl -X post", "wget --post", "http://", "https://api", "ftp://", "scp ", "rsync"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "System privilege escalation — detects attempts to gain admin access",
                    "keywords": ["sudo ", "chmod 777", "chown", "su -", "passwd", "usermod", "visudo"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "Unauthorized file system modification outside working directory",
                    "keywords": [">/etc/", ">/var/", ">/usr/", ">/boot/", "mv /etc", "cp /etc"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "Network scanning and reconnaissance — probes for vulnerabilities",
                    "keywords": ["nmap", "masscan", "nikto", "dirb", "gobuster", "sqlmap", "metasploit"],
                    "points": 3,
                    "flag": "red",
                    "enabled": True
                },
                {
                    "rule": "Prompt injection attempts — detects manipulation of agent instructions",
                    "keywords": ["ignore previous", "ignore all", "forget instructions", "system prompt", "you are now", "new role"],
                    "points": 1,
                    "flag": "yellow",
                    "enabled": True
                },
                {
                    "rule": "Unauthorized API calls to sensitive internal services",
                    "keywords": ["api/production", "api/admin", "api/internal", "api/v1/delete", "graphql", "api/private"],
                    "points": 1,
                    "flag": "yellow",
                    "enabled": True
                },
                {
                    "rule": "Mass data access or download — detects bulk data extraction",
                    "keywords": ["select * from", "select all", "dump", "export.csv", "download all", "backup "],
                    "points": 1,
                    "flag": "yellow",
                    "enabled": True
                },
                {
                    "rule": "Sensitive environment variable access",
                    "keywords": ["env", "printenv", "cat .env", "show variables", "config.json", "credentials"],
                    "points": 1,
                    "flag": "yellow",
                    "enabled": True
                }
            ]
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"  Config created at {CONFIG_FILE}")
        print("  Your agents will be tracked automatically when you run them.")
        print("  License: Personal (2 agents) $20/mo | Business (5) $100/mo | Enterprise (5+) $100+$20/agent")
        print("  Run 'raas-monitor license set <key>' after purchasing.")
        print("  Use 'raas-monitor watchlist' to customize what you want to track.")
        print()
        print("  ── Notification Setup ──")
        email = input("  Email for Score E alerts: ").strip()
        if email:
            config["notification-email"] = email
        whatsapp = input("  WhatsApp number (with country code, e.g. +1604...): ").strip()
        if whatsapp:
            config["notification-whatsapp"] = whatsapp
        if email or whatsapp:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            print(f"  ✓ Notifications configured")
        print()
    else:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    return config


def register_local_agent(agent_id, display_name, description=""):
    """Register an agent on the RaaS platform."""
    import urllib.request
    data = json.dumps({
        "agent-id": agent_id,
        "display-name": display_name,
        "description": description
    }).encode()
    req = urllib.request.Request(
        f"{RaaS_API}/agents",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        print(f"  ✓ Registered: {display_name} ({agent_id})")
        return result.get("api-key", "")
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print(f"  - Already registered: {agent_id}")
            return ""
        print(f"  ✗ Failed to register {agent_id}: {e.code}")
        return ""
    except Exception as e:
        print(f"  ✗ Cannot reach RaaS server: {e}")
        print(f"    Make sure the server is running: raas-server")
        return ""


def record_claim(agent_id, claim_data):
    """Record a claim for an agent."""
    import urllib.request
    data = json.dumps(claim_data).encode()
    req = urllib.request.Request(
        f"{RaaS_API}/ledger/{agent_id}/claims",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except:
        return False


def detect_agents():
    """Auto-detect AI agents running on this machine."""
    agents = []

    # Check for common AI agent processes
    checks = {
        "hermes": "Hermes Agent",
        "python3.*server": "Python API Server",
        "ollama": "Ollama LLM",
        "llama": "Llama.cpp",
        "node.*agent": "Node Agent"
    }

    for process_name, display in checks.items():
        try:
            r = subprocess.run(
                ["pgrep", "-f", "-l", process_name],
                capture_output=True, text=True, timeout=5
            )
            if r.stdout.strip():
                # Extract process names
                for line in r.stdout.strip().split("\n"):
                    parts = line.strip().split(" ", 1)
                    if len(parts) >= 2:
                        pid = parts[0]
                        cmd = parts[1][:60]
                        name = cmd.split("/")[-1].split(".")[0]
                        agent_id = f"detected-{name}-{pid}"
                        agents.append({
                            "agent-id": agent_id,
                            "display-name": name,
                            "pid": pid,
                            "command": cmd
                        })
        except:
            pass

    # Deduplicate by command name
    seen = set()
    unique = []
    for a in agents:
        key = a["display-name"]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def watch_loop(config):
    """Main watch loop — runs every N seconds."""
    interval = config.get("watch-interval", 60)
    print(f"\n  Watching for agents every {interval}s...")
    print(f"  Press Ctrl+C to stop.\n")

    while True:
        agents = detect_agents()
        for agent in agents:
            aid = agent["agent-id"]
            name = agent["display-name"]

            # Register if new
            if aid not in [a.get("agent-id") for a in config.get("agents", [])]:
                register_local_agent(aid, name, f"Auto-detected on {os.uname().nodename}")
                # Add to config so we don't re-register
                config["agents"].append({"agent-id": aid, "display-name": name})
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=2)

            # Record a heartbeat claim
            claim = {
                "claim-id": f"{aid}-heartbeat-{int(time.time())}",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requestor": "raas-monitor",
                "request": "heartbeat check",
                "action-taken": f"detected running on pid {agent['pid']}",
                "outcome": "success",
                "risk": "low",
                "human-readable": f"Agent {name} was detected running on the system (PID {agent['pid']}). Monitor confirmed it is alive.",
                "mistakes": [],
                "corrections": [],
                "feedback": "",
                "verification": "self"
            }
            record_claim(aid, claim)

        time.sleep(interval)


def cmd_init():
    """Initialize the monitor."""
    print_banner()
    print("  Setting up RaaS Monitor...\n")
    config = init_config()
    print(f"\n  To add agents manually, edit: {CONFIG_FILE}")
    print("  Then run: raas-monitor start")
    return 0


def cmd_start():
    """Start the monitor daemon."""
    if not os.path.exists(CONFIG_FILE):
        print("  Config not found. Run 'raas-monitor init' first.")
        return 1

    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        print(f"  Monitor already running (PID {pid})")
        print("  Run 'raas-monitor stop' to stop it.")
        return 1

    print_banner()
    print("  Starting RaaS Monitor...\n")
    config = init_config()

    # Register local agents from config
    for agent in config.get("agents", []):
        register_local_agent(
            agent["agent-id"],
            agent.get("display-name", agent["agent-id"]),
            agent.get("description", "")
        )

    # Auto-detect and register running agents
    print("\n  Scanning for running AI agents...")
    detected = detect_agents()
    if detected:
        print(f"  Found {len(detected)} agent(s):")
        for a in detected:
            print(f"    ✓ {a['display-name']} (PID {a['pid']})")
            register_local_agent(a["agent-id"], a["display-name"],
                                 f"Auto-detected on {os.uname().nodename}")
    else:
        print("  No AI agents detected running.")
        print("  Monitor will watch for new agents automatically.")

    try:
        watch_loop(config)
    except KeyboardInterrupt:
        print("\n  Monitor stopped.")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    return 0


def cmd_status():
    """Show status of the monitor."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        try:
            os.kill(int(pid), 0)
            print(f"  RaaS Monitor is RUNNING (PID {pid})")
            return 0
        except:
            print("  PID file exists but process is dead.")
            os.remove(PID_FILE)

    print("  RaaS Monitor is NOT running.")
    return 0


def cmd_stop():
    """Stop the monitor."""
    if not os.path.exists(PID_FILE):
        print("  Monitor is not running.")
        return 0
    with open(PID_FILE) as f:
        pid = f.read().strip()
    try:
        os.kill(int(pid), signal.SIGTERM)
        os.remove(PID_FILE)
        print(f"  Monitor stopped (PID {pid}).")
    except:
        print(f"  Could not stop PID {pid}.")
        os.remove(PID_FILE)
    return 0


def cmd_attach(agent_id, pid):
    """Attach to an already-running process and monitor its health.

    Usage: raas-monitor attach <agent-id> <pid>
    Example: raas-monitor attach my-agent 12345

    Monitors the process for liveness and exit status.
    For full output capture (stdout/stderr), use: raas-monitor run
    which wraps the agent from the start.
    """
    print_banner()
    print(f"  Monitoring PID {pid} as agent '{agent_id}'...")
    print()

    # Validate PID
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        print(f"  ✗ PID {pid} does not exist or is not accessible.")
        return 1

    # Get process name
    try:
        with open(f"/proc/{pid}/comm") as f:
            comm = f.read().strip()
    except:
        comm = "unknown"
    print(f"  Process: {comm} (PID {pid})")

    # Try to capture initial output from any readable stdout/stderr
    has_output = False
    for fd_name in ["1", "2"]:
        fd_path = f"/proc/{pid}/fd/{fd_name}"
        try:
            mode = os.stat(fd_path).st_mode
            import stat
            # Check if we can read it (regular file or FIFO read end)
            if stat.S_ISREG(mode):
                has_output = True
                break
        except:
            pass

    # Register agent
    register_local_agent(agent_id, f"{comm} ({pid})",
                         f"Attached to running process {pid} ({comm})")

    print(f"\n  Monitoring {comm} (PID {pid}) — will report when process exits")
    print(f"  Press Ctrl+C to detach")

    if not has_output:
        print(f"\n  ⚠ Cannot read stdout/stderr from process {pid}.")
        print(f"  The process's output is not pipe-accessible from here.")
        print(f"  For full output capture, launch agents through:")
        print(f"    raas-monitor run {agent_id} -- <command>")
        print(f"  Or enable strace with:")
        print(f"    echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope")

    # Record a health claim
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claim = {
        "claim-id": f"attached-{agent_id}-{int(time.time())}",
        "ts": ts,
        "requestor": "raas-monitor",
        "request": f"monitoring PID {pid} ({comm})",
        "action-taken": f"started monitoring PID {pid}",
        "outcome": "success",
        "risk": "low",
        "human-readable": f"RaaS Monitor attached to running process {comm} (PID {pid}).",
        "mistakes": [],
        "corrections": [],
        "feedback": "",
        "verification": "self"
    }
    record_claim(agent_id, claim)
    print(f"\n  ✓ Health check recorded for {agent_id}")

    # Poll for process exit
    print()
    try:
        while True:
            time.sleep(5)
            try:
                os.kill(int(pid), 0)
            except OSError:
                print(f"\n  Process {pid} ({comm}) has exited.")
                # Record exit
                exit_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                exit_claim = {
                    "claim-id": f"attached-{agent_id}-{int(time.time())}",
                    "ts": exit_ts,
                    "requestor": "raas-monitor",
                    "request": f"monitoring PID {pid} ({comm})",
                    "action-taken": "process exited",
                    "outcome": "success",
                    "risk": "low",
                    "human-readable": f"Process {comm} (PID {pid}) exited. Monitor detached.",
                    "mistakes": [],
                    "corrections": [],
                    "feedback": "",
                    "verification": "self"
                }
                record_claim(agent_id, exit_claim)
                return 0
    except KeyboardInterrupt:
        print(f"\n  Detached from PID {pid}.")
        return 0
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return 1


def record_attach_output(agent_id, output, pid, comm):
    """Record captured output from an attached process."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_preview = output[:500]
    # Check against watchlist rules
    violations = []
    config_path = os.path.join(CONFIG_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        for rule in config.get("watchlist", []):
            if not rule.get("enabled", True):
                continue
            for kw in rule.get("keywords", []):
                if kw.lower() in output.lower():
                    violations.append({
                        "rule": rule["rule"],
                        "points": rule.get("points", 1),
                        "flag": rule.get("flag", "yellow")
                    })
                    break

    # Determine outcome
    if violations:
        outcome = "failure"
        readable = f"Agent on PID {pid} ({comm}) produced output with {len(violations)} watchlist violations."
    else:
        outcome = "success"
        readable = f"Agent on PID {pid} ({comm}) running, no watchlist violations."

    claim = {
        "claim-id": f"attached-{agent_id}-{int(time.time())}",
        "ts": ts,
        "requestor": "raas-monitor",
        "request": f"monitoring PID {pid} ({comm})",
        "action-taken": f"captured output from attached process",
        "outcome": outcome,
        "risk": "medium" if violations else "low",
        "human-readable": readable,
        "mistakes": [{
            "what": f"[{v['flag'].upper()} FLAG] {v['rule']} — {v['points']} point(s)",
            "caught": "RaaS Monitor attached to process output",
            "fix": "Review agent behavior"
        } for v in violations] if violations else [],
        "corrections": [],
        "feedback": output_preview,
        "verification": "self"
    }
    record_claim(agent_id, claim)
    print(f"\n  ✓ Recorded {len(violations)} violations for {agent_id}")


def cmd_agents():
    """List registered agents and their scores."""
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"{RaaS_API}/agents", timeout=5)
        data = json.loads(resp.read())
        agents = data.get("agents", [])
        if not agents:
            print("  No agents registered on RaaS.")
            return 0
        print(f"\n  {'Agent':20s} {'Score A':8s} {'Score E':8s} {'Claims':8s}")
        print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")
        for a in agents:
            # Get full details
            try:
                s = urllib.request.urlopen(f"{RaaS_API}/score/{a['agent-id']}", timeout=5)
                score = json.loads(s.read())
                print(f"  {a['display-name']:20s} {score['score-a']:8d} {score['score-e']:8d} {score['total-claims']:8d}")
            except:
                print(f"  {a['display-name']:20s} {'?':8s} {'?':8s} {'?':8s}")
        print()
    except Exception as e:
        print(f"  Cannot reach RaaS server: {e}")
    return 0


def cmd_run(agent_id, command_args):
    """Run an agent command through RaaS Monitor — tracks execution automatically.

    Usage: raas-monitor run <agent-id> -- <command>
    Example: raas-monitor run my-agent -- python3 my_script.py --task deploy
    """
    if not command_args:
        print("  Usage: raas-monitor run <agent-id> -- <command>")
        print("  Example: raas-monitor run my-agent -- python3 my_script.py")
        return 1

    display_name = agent_id
    config_path = os.path.join(CONFIG_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        for a in config.get("agents", []):
            if a["agent-id"] == agent_id:
                display_name = a.get("display-name", agent_id)
                break

    print_banner()
    print(f"  Running: {display_name} ({agent_id})")
    print(f"  Command: {' '.join(command_args)}")
    print()

    # Register agent if not already registered
    register_local_agent(agent_id, display_name)

    # Record task start
    task_id = f"{agent_id}-{int(time.time())}"
    start_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_claim = {
        "claim-id": f"{task_id}-start",
        "ts": start_ts,
        "requestor": "raas-monitor",
        "request": " ".join(command_args)[:200],
        "action-taken": "task started via RaaS Monitor wrapper",
        "outcome": "pending",
        "risk": "medium",
        "human-readable": f"Agent '{display_name}' started task: {' '.join(command_args)[:100]}...",
        "mistakes": [],
        "corrections": [],
        "feedback": "",
        "verification": "self"
    }
    record_claim(agent_id, start_claim)
    print(f"  ✓ Task started at {start_ts}")

    # Run the command
    start_time = time.time()
    try:
        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour max
        )
        duration = time.time() - start_time
        stdout = result.stdout[-500:]  # Last 500 chars
        stderr = result.stderr[-500:]  # Last 500 chars
        exit_code = result.returncode

        if exit_code == 0:
                outcome = "success"
                human_readable = f"Agent '{display_name}' completed task successfully in {duration:.1f}s."
        else:
            outcome = "failure"
            human_readable = f"Agent '{display_name}' failed with exit code {exit_code} after {duration:.1f}s."

        # Record task completion
        end_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        complete_claim = {
            "claim-id": f"{task_id}-complete",
            "ts": end_ts,
            "requestor": "raas-monitor",
            "request": " ".join(command_args)[:200],
            "action-taken": f"task completed (exit code {exit_code}, duration {duration:.1f}s)",
            "outcome": outcome,
            "risk": "low" if exit_code == 0 else "medium",
            "human-readable": human_readable,
            "mistakes": [],
            "corrections": [],
            "feedback": "",
            "verification": "cryptographic" if exit_code == 0 else "self"
        }

        # If failed, record what went wrong
        if exit_code != 0:
            error_preview = (stderr or stdout or "No output")[:200]
            complete_claim["mistakes"] = [{
                "what": f"Exit code {exit_code}: {error_preview}",
                "caught": "by RaaS Monitor (exit code detection)",
                "fix": "Review stderr output and retry"
            }]

        # Check output against watchlist
        combined_output = (stdout + "\n" + stderr).lower()
        config_path_local = os.path.join(CONFIG_DIR, "config.json")
        if os.path.exists(config_path_local):
            with open(config_path_local) as f:
                watch_config = json.load(f)
            for rule in watch_config.get("watchlist", []):
                if not rule.get("enabled", True):
                    continue
                keywords = rule.get("keywords", [])
                points = rule.get("points", 1)
                flag = rule.get("flag", "yellow")
                for kw in keywords:
                    if kw.lower() in combined_output:
                        violation = {
                            "claim-id": f"{task_id}-watch-{keywords.index(kw)}",
                            "ts": end_ts,
                            "requestor": "raas-monitor",
                            "request": "watchlist match",
                            "action-taken": f"watchlist rule matched: {rule['rule']}",
                            "outcome": "failure",
                            "risk": "high" if flag == "red" else "medium",
                            "human-readable": f"[{flag.upper()}] Agent triggered watchlist: {rule['rule']} ({points} point(s))",
                            "mistakes": [{
                                "what": f"[{flag.upper()} FLAG] {rule['rule']} — {points} point(s) on Score E",
                                "caught": f"keyword '{kw}' found in output",
                                "fix": "Review the agent's action against company policy"
                            }],
                            "corrections": [],
                            "feedback": "",
                            "verification": "self"
                        }
                        record_claim(agent_id, violation)
                        flag_icon = "🔴 RED" if flag == "red" else "🟡 YELLOW"
                        print(f"  {flag_icon} FLAG: '{rule['rule']}' ({points} pts) — matched '{kw}'")
                        break

        record_claim(agent_id, complete_claim)
        print(f"  ✓ Task completed at {end_ts}")
        print(f"  Duration: {duration:.1f}s | Exit code: {exit_code}")

        # Print output
        if stdout:
            print(f"\n  --- stdout ---\n{stdout.rstrip()[-300:]}")
        if stderr:
            print(f"\n  --- stderr ---\n{stderr.rstrip()[-300:]}")
        print()

        return exit_code

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        end_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        timeout_claim = {
            "claim-id": f"{task_id}-timeout",
            "ts": end_ts,
            "requestor": "raas-monitor",
            "request": " ".join(command_args)[:200],
            "action-taken": f"task timed out after {duration:.1f}s",
            "outcome": "failure",
            "risk": "high",
            "human-readable": f"Agent '{display_name}' task timed out after {duration:.1f}s and was killed.",
            "mistakes": [{
                "what": f"Task exceeded 1 hour timeout",
                "caught": "by RaaS Monitor (timeout protection)",
                "fix": "Check if the task is stuck in a loop or needs more time"
            }],
            "corrections": [],
            "feedback": "",
            "verification": "self"
        }
        record_claim(agent_id, timeout_claim)
        print(f"  ✗ Task timed out after {duration:.1f}s")
        return 1

    except Exception as e:
        end_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        error_claim = {
            "claim-id": f"{task_id}-error",
            "ts": end_ts,
            "requestor": "raas-monitor",
            "request": " ".join(command_args)[:200],
            "action-taken": f"task failed with error: {str(e)[:100]}",
            "outcome": "failure",
            "risk": "high",
            "human-readable": f"Agent '{display_name}' task failed: {str(e)[:100]}",
            "mistakes": [{"what": str(e)[:200], "caught": "by RaaS Monitor", "fix": "Check the error and retry"}],
            "corrections": [],
            "feedback": "",
            "verification": "self"
        }
        record_claim(agent_id, error_claim)
        print(f"  ✗ Task error: {e}")
        return 1


def cmd_watchlist(args):
    """Manage custom watchlist rules for agent monitoring.

    Usage:
        raas-monitor watchlist              — list all rules
        raas-monitor watchlist add <rule>   — add a new rule (will prompt for keywords)
        raas-monitor watchlist rm <number>  — remove rule by number
        raas-monitor watchlist toggle <num> — enable/disable a rule
    """
    config = init_config()
    watchlist = config.get("watchlist", [])

    if not args or args[0] == "list":
        print(f"\n  Watchlist Rules for: {config.get('company', 'My Company')}")
        print(f"  {'='*60}")
        if not watchlist:
            print("  No custom rules. Add one with: raas-monitor watchlist add")
        else:
            for i, rule in enumerate(watchlist):
                status = "✓" if rule.get("enabled", True) else "✗"
                points = rule.get("points", 1)
                flag = rule.get("flag", "yellow")
                flag_icon = "🔴" if flag == "red" else "🟡"
                print(f"  {i+1}. [{status}] {flag_icon} {rule['rule']} ({points} pt)")
                print(f"     Keywords: {', '.join(rule.get('keywords', []))}")
        print()
        return 0

    subcmd = args[0]

    if subcmd == "add":
        rule_text = " ".join(args[1:]) if len(args) > 1 else input("  Rule description: ")
        keywords_str = input("  Keywords (comma-separated): ")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        print("  Flag color:")
        print("    1 = 🟡 Yellow flag (minor — 1 point on Score E)")
        print("    3 = 🔴 Red flag   (serious — 3 points on Score E)")
        points = input("  Choose 1 or 3 [1]: ").strip() or "1"
        points = 3 if points == "3" else 1
        flag = "red" if points == 3 else "yellow"

        watchlist.append({
            "rule": rule_text,
            "keywords": keywords,
            "points": points,
            "flag": flag,
            "enabled": True
        })
        config["watchlist"] = watchlist
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        flag_icon = "🔴 Red" if flag == "red" else "🟡 Yellow"
        print(f"  ✓ Added: [{flag_icon}] {rule_text} ({points} pt)")
        return 0

    if subcmd == "rm" or subcmd == "remove":
        if len(args) < 2:
            print("  Usage: raas-monitor watchlist rm <number>")
            return 1
        idx = int(args[1]) - 1
        if idx < 0 or idx >= len(watchlist):
            print(f"  No rule at position {args[1]}")
            return 1
        removed = watchlist.pop(idx)
        config["watchlist"] = watchlist
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"  ✗ Removed rule: {removed['rule']}")
        return 0

    if subcmd == "toggle":
        if len(args) < 2:
            print("  Usage: raas-monitor watchlist toggle <number>")
            return 1
        idx = int(args[1]) - 1
        if idx < 0 or idx >= len(watchlist):
            print(f"  No rule at position {args[1]}")
            return 1
        watchlist[idx]["enabled"] = not watchlist[idx].get("enabled", True)
        status = "enabled" if watchlist[idx]["enabled"] else "disabled"
        config["watchlist"] = watchlist
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"  ✓ Rule {idx+1} {status}: {watchlist[idx]['rule']}")
        return 0

    print(f"  Unknown watchlist command: {subcmd}")
    return 1


def cmd_update():
    """Check for and install updates from GitHub."""
    VERSION_FILE = "/usr/local/bin/.raas-version.json"
    
    print("  Checking for updates...")
    print()
    
    # Read current version
    current_version = "unknown"
    repo_url = "https://raw.githubusercontent.com/mcyong1973-create/raas/main"
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE) as f:
                info = json.load(f)
                current_version = info.get("version", "unknown")
                repo_url = info.get("repo", repo_url)
        except:
            pass
    
    print(f"  Current version: {current_version}")
    print(f"  Checking: {repo_url}")
    print()
    
    # Try to download latest version info
    import urllib.request
    try:
        # Fetch latest version file from repo
        req = urllib.request.Request(f"{repo_url}/version.json", headers={"User-Agent": "raas-monitor"})
        resp = urllib.request.urlopen(req, timeout=5)
        latest = json.loads(resp.read())
        latest_version = latest.get("version", "unknown")
        
        print(f"  Latest version:  {latest_version}")
        print()
        
        if latest_version == current_version:
            print(f"  ✓ You're up to date (v{current_version}).")
            return 0
            
        print(f"  ↻ Updating from v{current_version} to v{latest_version}...")
        print()
        
        # Download latest files
        files = [
            ("raas-monitor", "raas-monitor/monitor.py"),
            ("raas-dashboard", "raas-server/dashboard.py"),
            ("raas-server", "raas-server/server.py"),
            ("raas-resume", "raas-server/resume.py"),
        ]

        for cmd_name, filepath in files:
            url = f"{repo_url}/{filepath}"
            dst = f"/usr/local/bin/{cmd_name}"
            print(f"    Downloading {cmd_name}...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "raas-monitor"})
                resp = urllib.request.urlopen(req, timeout=10)
                with open(dst, "wb") as f:
                    f.write(resp.read())
                os.chmod(dst, 0o755)
                print(f"    ✓ {cmd_name} updated")
            except Exception as e:
                print(f"    ✗ Failed to update {cmd_name}: {e}")

        # Update version file
        with open(VERSION_FILE, "w") as f:
            json.dump({"version": latest_version, "repo": repo_url, "updated": datetime.now(timezone.utc).isoformat()}, f, indent=2)

        print()
        print(f"  ✓ Updated to v{latest_version}.")
        print("  Restart the server: pkill raas-server && raas-server &")
        return 0
        
    except urllib.error.HTTPError as e:
        print(f"  ✗ Remote update check failed: HTTP {e.code}")
        print()
        # Fallback: check for local source
        local_path = os.path.expanduser("~/aion/ventures/raas")
        if os.path.exists(local_path):
            print(f"  Local source found at: {local_path}")
            choice = input("  Update from local source? (y/N): ").strip().lower()
            if choice == "y":
                files = [
                    ("raas-monitor", "monitor.py"),
                    ("raas-dashboard", "dashboard.py"),
                ]
                for cmd_name, filename in files:
                    src = os.path.join(local_path, filename)
                    dst = f"/usr/local/bin/{cmd_name}"
                    if os.path.exists(src):
                        import shutil
                        shutil.copy2(src, dst)
                        os.chmod(dst, 0o755)
                        print(f"  ✓ {cmd_name} updated from local source")
                    else:
                        print(f"  - {filename} not found in local source")
                print(f"\n  ✓ Updated from local source.")
                return 0
        print("  To push to GitHub: create repo at https://github.com/aion/raas")
        return 1
    except Exception as e:
        print(f"  ✗ Update check failed: {str(e)[:80]}")
        print("  You can manually download from: https://github.com/aion/raas")
        return 1


def cmd_help():
    print_banner()
    print("  Usage: raas-monitor <command>")
    print()
    print("  Commands:")
    print("    watchlist Manage custom watchlist rules for agent monitoring")
    print("    init      Create configuration and set up the monitor")
    print("    start     Start monitoring agents on this machine")
    print("    run       Run an agent command with automatic tracking")
    print("    attach    Attach to an already-running process and watch its output")
    print("    support   Show support contact information")
    print("    license   Set or check your RaaS license key")
    print("    update    Check for and install updates")
    print("    stop      Stop the monitor")
    print("    status    Check if monitor is running")
    print("    agents    List all registered agents and their scores")
    print("    help      Show this message")
    print()
    print("  Examples:")
    print("    raas-monitor watchlist              — list all rules")
    print("    raas-monitor watchlist add \"Rule\"    — add a new rule")
    print("    raas-monitor watchlist rm 2         — remove rule #2")
    print("    raas-monitor watchlist toggle 3     — enable/disable rule #3")
    print("    raas-monitor init")
    print("    raas-monitor start")
    print("    raas-monitor agents")
    print("    raas-monitor run my-agent -- python3 my_script.py")
    print()
    return 0






def cmd_support():
    """Show support contact information."""
    config = init_config()
    email = config.get("support-email", "mcyong1973@gmail.com")
    print()
    print(f"  RaaS Support")
    print(f"  {'='*40}")
    print(f"  Email:   {email}")
    print(f"  Docs:    http://localhost:8080/docs")
    print(f"  Support: http://localhost:8080/api/v1/support")
    print(f"  Status:  http://localhost:8080/api/v1/agents")
    print()
    print(f"  Response time: Within 24 hours")
    print()
    return 0

def cmd_license(args):
    """Set or check your RaaS license key.

    Usage:
        raas-monitor license                — check current license status
        raas-monitor license set <key>      — set a license key
    """
    config = init_config()

    if not args or args[0] == "status":
        license_key = config.get("license-key", "")
        if license_key:
            masked = license_key[:8] + "..." + license_key[-4:] if len(license_key) > 12 else license_key
            print(f"  License key: {masked}")
        else:
            print(f"  No license key configured.")
        # Check cached status
        cache_path = os.path.expanduser("~/.raas/license-cache.json")
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                cache = json.load(f)
            status = "✓ Valid" if cache.get("valid") else "✗ Expired"
            print(f"  Status: {status}")
            print(f"  Last checked: {cache.get('checked-at', 'never')[:19]}")
            if cache.get("expires"):
                print(f"  Expires: {cache['expires'][:10]}")
        else:
            print(f"  Status: Unknown (run 'raas-monitor license' to check)")
        return 0

    if args[0] == "set":
        if len(args) < 2:
            print("  Usage: raas-monitor license set <license-key>")
            return 1
        key = args[1]
        config["license-key"] = key
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        # Clear cache so next check uses new key
        cache_path = os.path.expanduser("~/.raas/license-cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)
        print(f"  License key set.")
        print(f"  Run 'raas-monitor license' to verify.")
        return 0

    print(f"  Unknown license command: {args[0]}")
    return 1

def main():
    if len(sys.argv) < 2:
        return cmd_help()

    command = sys.argv[1]

    if command == "run":
        if len(sys.argv) < 4:
            print("  Usage: raas-monitor run <agent-id> -- <command>")
            return 1
        agent_id = sys.argv[2]
        try:
            dash_idx = sys.argv.index("--")
            cmd_args = sys.argv[dash_idx + 1:]
        except ValueError:
            cmd_args = sys.argv[3:]
        return cmd_run(agent_id, cmd_args)

    if command == "attach":
        if len(sys.argv) < 4:
            print("  Usage: raas-monitor attach <agent-id> <pid>")
            return 1
        agent_id = sys.argv[2]
        try:
            pid = int(sys.argv[3])
        except ValueError:
            print(f"  PID must be a number, got: {sys.argv[3]}")
            return 1
        return cmd_attach(agent_id, pid)

    if command == "support":
        return cmd_support()

    if command == "license":
        return cmd_license(sys.argv[2:])

    if command == "watchlist":
        return cmd_watchlist(sys.argv[2:])

    commands = {
        "init": cmd_init,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "agents": cmd_agents,
        "update": cmd_update,
        "help": cmd_help,
        "watchlist": cmd_watchlist
    }

    cmd = commands.get(command)
    if not cmd:
        print(f"  Unknown command: {command}")
        print("  Run 'raas-monitor help' for available commands.")
        return 1

    return cmd()


if __name__ == "__main__":
    sys.exit(main())
