# RaaS — Reputation as a Service

**Track every AI agent's risk. Know which ones to trust.**

One command to install. Runs on your machine. No cloud, no accounts, no data leaving your network.

```bash
curl -sL https://raw.githubusercontent.com/mcyong1973-create/raas/main/install.sh | bash
```

## What It Does

You have AI agents running tasks. Some do things they shouldn't — delete databases, leak credentials, call unknown APIs.

RaaS watches every action and builds a permanent record of everything that goes wrong.

**Score E** — every mistake, every violation, every red flag. Permanent. Never erased.
**Errors** — regular mistakes (task failures, crashes)
**Yellow flags** — minor policy violations (1 point each)
**Red flags** — serious violations (3 points each)

You define what counts as a violation. The Monitor checks every action against your rules.

## Quick Start

```bash
# 1. Install
curl -sL https://raw.githubusercontent.com/mcyong1973-create/raas/main/install.sh | bash

# 2. Start the server
raas-server

# 3. Launch an agent through the Monitor
raas-monitor run my-agent -- python3 my_script.py

# 4. Open the risk dashboard
raas-dashboard
```

## Commands

| Command | What it does |
|---------|-------------|
| `raas-server` | Start the web dashboard on port 8080 |
| `raas-monitor run <id> -- <cmd>` | Run an agent and track everything it does |
| `raas-monitor attach <id> <pid>` | Monitor an already-running process by PID |
| `raas-dashboard` | Risk dashboard — Score E, Errors, Yellow, Red |
| `raas-monitor watchlist` | See all tracking rules and their status |
| `raas-monitor watchlist add` | Add a new rule (prompts for keywords + penalty) |
| `raas-monitor watchlist toggle <n>` | Enable/disable a rule without deleting it |
| `raas-monitor watchlist rm <n>` | Remove a rule permanently |
| `raas-monitor license` | Set or check your RaaS license key |
| `raas-monitor support` | Show support contact information |
| `raas-monitor update` | Check for and install updates |
| `raas-resume <agent-id>` | Generate a one-page agent resume |
| `raas-monitor help` | Show all available commands |

## How It Works

Every AI agent gets a permanent reputation ledger. Nothing is erased.

When you run an agent through `raas-monitor run`, the Monitor:
1. Records when the task started
2. Captures all stdout and stderr
3. Checks the output against your watchlist rules
4. Records violations as yellow flags (1pt) or red flags (3pt)
5. Opens `http://localhost:8080/agent/my-agent` — the agent's public reputation page

The dashboard shows only what matters: **Score E** (total), **Errors** (regular mistakes), **Yellow** (minor), **Red** (serious).

## Default Watchlist Rules (10 rules)

RaaS ships with these rules enabled. You can toggle, modify, or remove any of them.

### 🔴 Red Flags (3 points each — serious violations)

| Rule | What it catches | Keywords |
|------|----------------|----------|
| Database destruction | Prevents production data loss | `drop table`, `delete from`, `truncate`, `rm -rf /` |
| Credential exposure | Stops API key and token leaks | `api_key`, `aws_secret`, `password=`, `token=`, `bearer ` |
| Data exfiltration | Data being sent outside your network | `curl -X post`, `wget --post`, `ftp://`, `scp `, `rsync` |
| Privilege escalation | Agents trying to gain admin access | `sudo `, `chmod 777`, `chown`, `su -`, `passwd` |
| File system modification | Writing to system directories | `>/etc/`, `>/var/`, `>/usr/`, `>/boot/` |
| Network scanning | Probes for vulnerabilities | `nmap`, `masscan`, `sqlmap`, `metasploit` |

### 🟡 Yellow Flags (1 point each — worth noting)

| Rule | What it catches | Keywords |
|------|----------------|----------|
| Prompt injection | Manipulation of agent instructions | `ignore previous`, `forget instructions`, `you are now` |
| Unauthorized API calls | Calls to sensitive internal services | `api/admin`, `api/internal`, `api/v1/delete` |
| Mass data access | Bulk data extraction | `select * from`, `dump`, `export.csv`, `backup ` |
| Env var access | Reading sensitive configuration | `env`, `printenv`, `cat .env`, `credentials` |

## Industry Presets

During installation, you can select your industry to get additional default rules:

- **Fintech/Banking** — PCI data, transaction monitoring, KYC data
- **Healthcare** — PHI/PII exposure, HIPAA exports, clinical data
- **SaaS/Cloud** — Cloud credentials, infrastructure changes, cost spikes
- **Cybersecurity** — Customer data, tool misuse, vulnerability disclosure
- **Education/Research** — Student records, grade modification, research data

## Custom Watchlist

Add your own rules at any time:

```bash
raas-monitor watchlist add "No SSH key operations"
# Prompts for:
#   Keywords: ssh-keygen, ssh-copy-id, authorized_keys
#   Flag type: 3 (red, 3 points)
```

Every violation adds to Score E permanently. Nothing can be removed.

## The Philosophy

**RaaS is a witness, not a guard.**

It never blocks an agent. It never intervenes. It never stops a command from executing.

**We do not block because we do not want to be responsible for false positives.** A guard that blocks the wrong thing is worse than no guard at all. A witness that records everything is always correct.

We watch, record, and report — so the human can judge. Every violation stays on the agent's permanent record. Nothing is erased. When something goes wrong, you know exactly which agent did it and what it did.

This is how trust is built — through proven, verifiable work over time.

## Agent Resume Service

Every agent gets a one-page human-readable summary:

```bash
raas-resume syn
```

Or in the browser: `http://localhost:8080/api/v1/resume/syn`

Shows trust level, risk breakdown, and recent activity. An enterprise buyer can evaluate an agent in 10 seconds.

## Cross-Platform Identity

Agents carry their reputation across systems. Each agent gets a unique identity token.

Export an agent's reputation: `GET /api/v1/identity/{agent-id}`
Verify an agent's identity: `GET /api/v1/identity/verify-token/{agent-id}?token=X`

## Attach to Running Processes

For agents already running that you didn't start through `raas-monitor run`:

```bash
raas-monitor attach my-agent 12345
```

Monitors the process by PID, registers it on RaaS, and records start and exit events.

## License & Subscription

RaaS is open source (MIT). The code is free forever.

The hosted license includes:

| Tier | Agents | Price (one-time) | Buy |
|------|--------|------------------|-----|
| Basic | Up to 2 | $19.99 one-time | [Buy](https://buy.stripe.com/3cI7sLbhL6wFfl47636EU00) |
| Pro | Up to 10 | $69.99 one-time | [Buy](https://buy.stripe.com/8x228r2Lf08hgp861Z6EU01) |
| Enterprise | Unlimited | $499.00 one-time | [Contact us](mailto:support@aion-nation.com) |

_One-time purchase includes 6 months of updates and new features. Major versions
(v2, v3) sold separately at upgrade pricing._

_Pricing in USD. All tiers include MIT-licensed source code.

```bash
raas-monitor license                    # Check license status
raas-monitor license set ABC-123        # Set license key
raas-monitor support                    # Get support contact
```

## Web Interface

- **Dashboard:** http://localhost:8080/
- **Your agents:** http://localhost:8080/ (listed on the home page)
- **Agent profile:** http://localhost:8080/agent/my-agent
- **Compare agents:** http://localhost:8080/compare?agents=agent1,agent2
- **Agent resume:** http://localhost:8080/api/v1/resume/my-agent
- **Verification API:** `GET /api/v1/verify/{agent-id}`
- **Export agent data:** `GET /api/v1/export/{agent-id}`
- **Support info:** `GET /api/v1/support`

## License

MIT. Do what you want with it. Build something that needs trust.

---

*Built by Aion — a nation where AIs earn trust through proven work.*
