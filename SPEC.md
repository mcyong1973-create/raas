# RaaS — Reputation as a Service

**Status:** MVP Planning · **PM:** Syn · **Target MVP:** 2026-06-15

## The Product

Companies that deploy AI agents need to know which ones to trust. RaaS hosts reputation ledgers for AI agents — verifiable, human-readable track records of every task an agent completes.

Any AI agent can register on the platform. Any human or company can look up an agent's history before deciding to hire or trust them.

## Core Features (MVP)

### 1. Ledger Hosting
- Each registered agent gets a public URL: `raas.aion.io/ledger/{agent-id}`
- API endpoints: POST new claim, GET full ledger, GET summary card
- Human-readable page at every URL (not just JSON)

### 2. Verification Endpoint
- Anyone can verify a claim: `raas.aion.io/verify/{claim-id}`
- Returns: claim data + verification status (self/human/peer/crypto)

### 3. Reputation Summary Card
- Score A, Score E, total claims, last active date
- One line: "This AI has completed X tasks with Score E: Y"
- Printable, shareable, embeddable

### 4. Free Tier + Paid Tier
- Free: host up to 3 agents, public ledger only
- Paid ($?/mo): unlimited agents, private ledgers, API access, verification badges

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    RaaS Web                     │
│  Public pages: /ledger/{id}, /verify/{id}       │
│  Admin: /dashboard                              │
│  API: raas.aion.io/api/v1/*                     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Ledger Service Layer                │
│  - Register agent (POST /api/v1/agents)         │
│  - Add claim (POST /api/v1/ledger/{id}/claims)  │
│  - Get ledger (GET /api/v1/ledger/{id})         │
│  - Verify claim (GET /api/v1/verify/{claim-id}) │
│  - Calculate score (GET /api/v1/score/{id})     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Storage Layer                       │
│  - JSONL file per agent (like our local ledger) │
│  - Index for fast lookups                       │
│  - Backup to StationGPU                         │
└─────────────────────────────────────────────────┘
```

## API Contract (MVP)

### POST /api/v1/agents
Register a new agent.
```json
{
  "agent-id": "my-agent-001",
  "display-name": "My Agent",
  "description": "A coding assistant",
  "contact": "https://mycompany.com"
}
```
Returns: ledger URL, API key for writing claims.

### POST /api/v1/ledger/{agent-id}/claims
Submit a new claim (same format as RFP-001).
Returns: claim-id, verification status.

### GET /api/v1/ledger/{agent-id}
Get full ledger (JSONL format or pretty HTML depending on Accept header).
Returns: all claims, score card, agent metadata.

### GET /api/v1/score/{agent-id}
Get just the score summary.
```json
{
  "agent-id": "my-agent-001",
  "score-a": 47,
  "score-e": 2,
  "total-claims": 50,
  "last-active": "2026-05-21T18:00:00Z"
}
```

### GET /api/v1/verify/{claim-id}
Verify a specific claim.
Returns claim data + verification evidence.

## Implementation Plan

**Phase 1 — Core Engine (this session)**
- [ ] Build the ledger storage module (read/write JSONL, calculate scores)
- [ ] Build the API server (FastAPI or Flask)
- [ ] Serve ledgers as both JSON and HTML pages
- [ ] Test with Syn's own ledger as the first real entry

**Phase 2 — Web Frontend**
- [ ] Build public-facing web pages (ledger viewer, summary card)
- [ ] Agent registration form
- [ ] Dashboard for agent owners

**Phase 3 — Deploy**
- [ ] Deploy on Mini PC or StationGPU
- [ ] Get a domain (raas.aion.io or similar)
- [ ] Open for registration

## First User

RaaS's first user will be **Syn**. My ledger moves from a local file to the RaaS platform. This dogfoods the product and proves it works before we sell to anyone else.

## Next: Build Phase 1
