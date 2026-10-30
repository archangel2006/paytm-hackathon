# Paytm Saathi: Platform & Backend API

**Paytm Saathi** is an autonomous AI teammate designed for Paytm field sales executives (FSEs) and customer support teams. Saathi owns a single business outcome for every merchant: **take them from lead to their first 10 successful transactions.**

This repository contains the backend platform services, database layer, simulation engine, and integration wiring built for the Paytm Build for India AI Hackathon (Track 3: Autonomous AI Teammates).

---

## 1. Architecture & Team Ownership

The project enforces strict folder ownership and interface separation:

| Area | Owner | Folder | Responsibility |
|---|---|---|---|
| **Platform** | Person 3 (This Build) | `server/`, `e2e/`, `scripts/`, `docs/`, root files | SQLite database, REST API, SSE stream, scheduler, seed data, simulation engine, adapters |
| **Agent** | Person 2 | `agent/` | Context builder, NLU, planner, guardrails, autonomy ladder, tools, BM25 retrieval |
| **Integrations** | Person 1 | `integrations/` | WhatsApp webhook, phone simulator channel, OCR & blur pre-check, mock KYC |

### Dependency & Wiring Contract
- `server/main.py` is the composition root that wires `agent` and `integrations` through dependency injection:
  ```python
  agent.configure(store=agent_store, channel=integrations.router, documents=integrations.documents, clock=clock)
  integrations.configure(store=integrations_store, on_incoming=agent.handle_incoming, clock=clock)
  ```
- Neither `agent/` nor `integrations/` imports `server/`. They communicate solely through the Protocols in `agent/ports.py` and `integrations/ports.py`.

---

## 2. Quick Start

### 1. Setup Virtual Environment
```bash
# Windows
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -e .
```

For OCR on arbitrary uploaded documents, install the native Tesseract OCR
executable and make sure `tesseract` is available on `PATH`. The Python
`pytesseract` package is installed with the project, but it does not include
the native executable. Synthetic demo documents have a deterministic fallback
when Tesseract is unavailable; other images will be reported as unreadable.

### 2. Seed Database
Seeds 306 synthetic merchants (including the 6 demo heroes) and creates an instantaneous reset snapshot (`saathi.seed.db`):
```bash
python -m server.db.seed
# or: make seed
```
Farida Sweets is the fully onboarded example, with approved synthetic PAN and address-proof records, a completed field visit, an active device, and 42 successful transactions.

### 3. Run FastAPI Backend
```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
# or: make dev
```
Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Configure Gemini for the simulator

The Gemini Developer API key and model are read server-side from `agent/.env`.
That file is ignored by Git; never commit or share it. Example settings:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-flash-lite-latest
LLM_API_KEY=<your Gemini API key>
LLM_TIMEOUT_SECONDS=15
```

The timeout leaves headroom above Gemini's 10-second minimum request deadline.
When Gemini is configured, low-confidence chat requests use it for intent,
planning, and policy-grounded reply generation. If Gemini is unavailable, the
agent falls back to the retrieved policy text. The simulator does not send real
WhatsApp messages without separate WhatsApp Business credentials.
Install the declared dependencies with `pip install -e .`, then restart the
backend so it loads the new environment settings. Verify
`http://localhost:8000/api/health` reports `llm_configured: true`, then send a
test message in the simulator. This connects Gemini to the app's agent; it does
not enable real WhatsApp delivery, which requires separate WhatsApp Business
Platform credentials and webhook configuration.

### 4. Run the Frontend
```bash
cd frontend
npm ci
npm run dev
```
Open [http://localhost:3000](http://localhost:3000). The frontend uses a
same-origin Next.js API proxy to connect to the backend at
`http://127.0.0.1:8000` by default. To use another backend, set
`SAATHI_BACKEND_URL` in the frontend server environment (the value is the
backend origin, without `/api`). If the backend has `SAATHI_API_KEY` configured,
set the same key in the frontend server environment; it is forwarded server-side
and is never exposed to browser JavaScript. Do not use a `NEXT_PUBLIC_` variable
for API credentials. Frontend checks: `npm test`, `npm run lint`, and
`npm run build`.

---

## 3. Testing & Verification

### Run Unit Tests (PL-01 to PL-16)
Tests database models, idempotency, illegal state transition guards, context bundle construction, append-only audit logging, clock advancement, and simulation determinism:
```bash
pytest server/tests -v
# or: make test
```

### Run End-to-End Acceptance Tests (AT-1 to AT-9)
Tests the 5 hero scenarios live through the API contract:
```bash
pytest e2e -v
# or: make e2e
```

### Run Simulation Report
Generates Monte Carlo 30-day projection on 300 synthetic leads across 30 random seeds, comparing Manual vs. Saathi-assisted workflows with 95% confidence intervals:
```bash
python -m server.simulation.report
# or: make sim
```

### Check Ownership Boundaries
Ensures that no files outside Platform ownership are modified and that import boundaries remain intact:
```bash
python scripts/check_ownership.py
# or: make check
```

---

## 4. REST API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, database connection, simulated clock offset |
| `GET` | `/api/briefing` | Morning briefing: overnight counts, daily route, top leads |
| `GET` | `/api/merchants` | Paginated lead list with category, state, and score filters |
| `GET` | `/api/merchants/{id}` | Merchant 360 profile, timeline, docs, visits, tickets |
| `GET` | `/api/merchants/{id}/next-action` | Preview of the planner's proposed next best action |
| `POST` | `/api/chat/{merchant_id}/message` | Inbound simulator message triggering the agent loop |
| `POST` | `/api/documents/{merchant_id}` | Multipart document upload for KYC quality pre-check |
| `GET` | `/api/actions` | List of proposed, approved, and executed actions |
| `POST` | `/api/actions/{id}/approve` | Human approval of an L2 action |
| `POST` | `/api/actions/{id}/reject` | Human rejection of an L2 action with override reason |
| `GET` | `/api/handoffs` | Escalation queue with structured context summaries |
| `POST` | `/api/handoffs/{id}/resolve` | Resolve escalation handoff |
| `GET` | `/api/autonomy` | Autonomy levels (L1, L2, L3) per action type |
| `PUT` | `/api/autonomy/{action_type}` | Dynamic autonomy promotion/demotion |
| `GET` | `/api/scoreboard` | Live KPIs, funnel metrics, and override rates |
| `POST` | `/api/simulation/run` | Execute 30-day simulation with parameter overrides |
| `GET` | `/api/simulation/{run_id}` | Retrieve simulation report and confidence intervals |
| `GET` | `/api/audit` | Append-only audit trail |
| `POST` | `/api/demo/reset` | Instantaneous DB restore from pristine snapshot (<1s) |
| `POST` | `/api/demo/advance` | Advance simulated clock and trigger due background jobs |
| `POST` | `/api/demo/device-event` | Simulate device install and transaction increments |
| `GET` | `/api/stream` | Server-Sent Events (SSE) live action feed |
| `GET` | `/api/events` | Polling fallback for live events |

The complete OpenAPI 3.1 specification is maintained in [`docs/openapi.json`](docs/openapi.json).
