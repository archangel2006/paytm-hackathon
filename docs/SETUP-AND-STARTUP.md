# Paytm Saathi setup and startup guide

This is the single local-development guide for the implemented Paytm Saathi
platform. It covers the Python backend, the Next.js frontend, the SQLite demo
database, the agent configuration, and the optional WhatsApp integration.

## What runs locally

| Component | Location | Default |
|---|---|---|
| FastAPI platform API | `server/` | `http://localhost:8000` |
| Agent loop | `agent/` | Loaded by the API |
| Simulator, documents, WhatsApp | `integrations/` | Loaded by the API |
| Next.js UI | `frontend/` | `http://localhost:3000` |
| Demo database | `saathi.db` | SQLite |

The database and external integrations use synthetic/mock data. The optional
WhatsApp path requires provider credentials and an HTTPS tunnel.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Git
- PowerShell, Command Prompt, Git Bash, or another shell

## 1. Create and activate the Python virtual environment

First verify that Python is available:

```powershell
python --version
```

The project requires Python 3.11 or newer. On this Windows setup, use
`python` rather than `py`: the `py` launcher is not installed. Create and
activate the environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Confirm that the virtual environment is active:

```powershell
python --version
python -c "import sys; print(sys.prefix)"
```

The second command should print a path ending in `.venv`. Activate the
environment again in every new backend terminal before running Python commands.

If `python` is also not recognized, install Python 3.11+ from
<https://www.python.org/downloads/windows/>. During installation, enable
**Add python.exe to PATH**, restart the terminal, and repeat the commands
above. The `py -3.11 -m venv .venv` command is an alternative only when the
Python launcher is installed.

If you use Command Prompt instead of PowerShell:

```bat
python -m venv .venv
.\.venv\Scripts\activate.bat
```

Python 3.12 and 3.13 can also be used. If PowerShell blocks activation, use
the virtual environment interpreter directly
(`.\.venv\Scripts\python.exe`) for all commands, or set the current-user
execution policy to `RemoteSigned`.

## 2. Install Python dependencies

Upgrade pip, then install the project dependencies from `pyproject.toml`:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable install adds the backend runtime and test dependencies, including
FastAPI, Uvicorn, SQLAlchemy, Pydantic, HTTPX, NumPy, OpenCV, OpenAI, and
pytest. Do not install these globally.

Install the additional integration dependencies when using document OCR,
synthetic document samples, or WhatsApp media handling:

```powershell
python -m pip install -r integrations\requirements.txt
```

This installs the integration-specific packages such as Pillow, Tesseract
bindings, RapidFuzz, and the integration test dependencies. The editable
install and this requirements file are both installed into `.venv`.

## 3. Install frontend dependencies

Open a second terminal and install the Node.js dependencies:

```powershell
cd frontend
npm install
cd ..
```

This installs the versions declared in `frontend\package.json`, including
Next.js, React, TypeScript, ESLint, and Tailwind CSS, into
`frontend\node_modules`. Repeat `npm install` after changing
`frontend\package.json`.

## 4. Configure environment files

Copy the templates from the repository root:

```powershell
Copy-Item .env.example .env
Copy-Item server\.env.example server\.env
Copy-Item agent\.env.example agent\.env
```

The default server configuration uses SQLite, allows the local frontend in
CORS, stores uploads in `./uploads`, and runs the scheduler every five
seconds. Set `LLM_API_KEY` in `agent\.env` for live OpenAI-backed NLU and
planning. The agent has keyword/planner fallbacks for local demo and test
runs. Never commit real `.env` files or expose the LLM key to the frontend.

For document/OCR and WhatsApp features, install the integration dependencies:

```powershell
python -m pip install -r integrations\requirements.txt
```

Configure these only when using live WhatsApp:

```text
WHATSAPP_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_VERIFY_TOKEN
WHATSAPP_APP_SECRET
WHATSAPP_API_VERSION
BLUR_THRESHOLD
UPLOAD_DIR
MAX_UPLOAD_MB
```

## 5. Seed the demo database

```powershell
python -m server.db.seed
```

The seed creates the SQLite tables and synthetic merchant data, including the
six demo heroes, and writes `saathi.seed.db` as the pristine reset snapshot.
Run this again whenever you want to rebuild the local demo state.

## 6. Start the backend

Use a terminal from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m server.db.seed
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

The API starts the database lifecycle, wires the agent and integrations,
starts the background scheduler, and mounts the REST and WhatsApp routers.
Keep this terminal open.

Useful URLs:

- Health: <http://localhost:8000/api/health>
- Swagger UI: <http://localhost:8000/docs>
- OpenAPI: <http://localhost:8000/openapi.json>

Verify the service from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

## 7. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The UI includes the home/demo entry point,
dashboard, merchant list, merchant detail, approvals, handoffs, scoreboard,
autonomy controls, and phone-simulator interactions. The frontend demo state
is local to the browser; use the backend Swagger UI or API endpoints for the
persisted platform behavior.

## 6. Run the implemented demo controls

Reset to the pristine seeded state:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/demo/reset
```

Advance the simulated clock and execute due jobs:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/demo/advance `
  -ContentType "application/json" `
  -Body '{"hours":24}'
```

Initialize a hero scenario:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/demo/trigger/rahul
```

Simulate installation or transactions:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/demo/device-event `
  -ContentType "application/json" `
  -Body '{"merchant_id":"m_rahul","event":"installed"}'

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/demo/device-event `
  -ContentType "application/json" `
  -Body '{"merchant_id":"m_rahul","event":"transaction","count":1,"amount":150}'
```

The supported hero scenario names are `rahul`, `meena`, `sunil`, `farida`,
`vikram`, and `pooja`.

## 7. Run tests and checks

With the virtual environment active, run:

```powershell
python -m pytest server/tests -v
python -m pytest agent/tests -v
python -m pytest integrations/tests -v
python -m pytest e2e -v
python scripts/check_ownership.py
```

Run the deterministic simulation report:

```powershell
python -m server.simulation.report
```

The Makefile provides equivalent shortcuts: `make setup`, `make seed`,
`make dev`, `make test`, `make e2e`, `make sim`, and `make check`. The
PowerShell copy commands above are preferred on native Windows because the
Makefile setup target uses `cp`.

## 8. Optional WhatsApp startup

The webhook endpoint is:

```text
http://localhost:8000/webhooks/whatsapp
```

An external provider cannot call `localhost`. Start an HTTPS tunnel to port
8000, for example:

```text
cloudflared tunnel --url http://localhost:8000
```

Register the resulting HTTPS URL plus `/webhooks/whatsapp` with Meta. The
implementation verifies the webhook token and HMAC signature, deduplicates
event IDs, parses text/media/status events, downloads media when needed, and
returns provider-safe results. Use the phone simulator if a tunnel or provider
is unavailable.

## Troubleshooting

### Port already in use

Use another API port:

```powershell
python -m uvicorn server.main:app --host 0.0.0.0 --port 8001 --reload
```

Update `CORS_ORIGINS` in `server\.env` if the frontend origin changes.

### Seed or database errors

Run the seed command from the repository root so relative SQLite paths resolve:

```powershell
python -m server.db.seed
```

### Missing Python package

Confirm the virtual environment is active, then reinstall:

```powershell
python -m pip install -e .
python -m pip install -r integrations\requirements.txt
```

### Frontend dependency or build errors

```powershell
cd frontend
npm install
npm run lint
npm run build
```
