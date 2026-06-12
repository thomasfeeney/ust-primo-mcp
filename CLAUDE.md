# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

MCP server (proof of concept) exposing the UST library catalog (Alma/Primo VE,
CLIC/MnPALS) to AI assistants, plus a landing page that doubles as the
documentation and demo. Pitched to UST Libraries/ITS by Tom Feeney; modeled on
Yale's and Northeastern's library MCP pilots.

**Status**: deployed at https://ust-primo-mcp-642962079239.us-central1.run.app
**Repository**: https://github.com/thomasfeeney/ust-primo-mcp

## Tech Stack

- Python 3.12, official `mcp` SDK (FastMCP, stateless streamable HTTP)
- Starlette + uvicorn (single ASGI app: landing page, demo API, MCP endpoint)
- httpx for outbound calls to Primo
- Google Cloud Run, deployed via GitHub Actions + WIF (same recipe as
  sep-copyediting-assistant)

## Architecture

- `primo.py` — Primo VE client + PNX record normalization. Key constants:
  `VID = 01CLIC_STTHOMAS:MNPALS`, scopes `ust` → `MyInstitution` (local only,
  the default — Ex Libris CDI licensing is unresolved) and `ust_plus_articles`
  → `MyInst_and_CI`. Uses the UI-internal `pub/pnxs` endpoint (no key needed);
  the sanctioned `external/pnxs` endpoint caps at 10 results — see landing
  page decision #2.
- `server.py` — FastMCP server, tools `search_catalog` and `get_record`.
  `get_record` works by *searching* for the record ID (direct
  `/pnxs/L/{id}` fetch returns an empty envelope on this host).
- `app.py` — mounts everything; MCP protocol lands at `/mcp`.
- `templates/index.html` + `static/style.css` — landing page (UST purple
  #510C76, Georgia serif). The "key decisions" section is the institutional
  pitch — keep it current if the code's defaults change.

## Development

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py            # localhost:8080
```

Quick MCP smoke test (initialize + tool call) — the endpoint requires the
client to send `Accept: application/json, text/event-stream`.

## Constraints & gotchas

- The Primo endpoint is unauthenticated but UI-internal; if Ex Libris adds
  referer/origin checks this breaks — fall back to `external/pnxs`.
- Keep the default scope local-only until the library resolves the CDI
  contract question (Scott Kaihoi, UST Libraries, is the contact).
- Stateless + JSON-response mode on FastMCP is required for Cloud Run
  (multiple instances, no session affinity).
- No query logging by design — stated on the landing page; don't add it.

## Deployment

- GCP project: `ust-primo-mcp`, region `us-central1`, service `ust-primo-mcp`.
- Push to `main` deploys via `.github/workflows/deploy.yml` (needs GitHub
  secrets `GCP_PROJECT_ID`, `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`).
- Manual: `gcloud run deploy ust-primo-mcp --source . --region us-central1 --allow-unauthenticated`
