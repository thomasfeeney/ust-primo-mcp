# UST Library Search × Claude — MCP Proof of Concept

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants (Claude
first; the protocol is vendor-neutral) search the University of St. Thomas
library catalog directly, so answers come from the library's curated records
with permalinks back to the real items.

**The deployed landing page is the documentation** — what this is, a live demo,
how to connect it to Claude, and the key decisions an institutional adoption
would need to settle: **https://ust-primo-mcp-642962079239.us-central1.run.app**
(MCP endpoint: same URL + `/mcp`). Everything below is developer detail.

## How it works

```
Claude  ──MCP (streamable HTTP)──►  this server  ──HTTPS──►  Primo VE public search API
                                    (Cloud Run)              librarysearch.stthomas.edu
```

- `server.py` — the MCP server (official `mcp` SDK / FastMCP, stateless
  streamable HTTP). Two tools: `search_catalog`, `get_record`.
- `primo.py` — thin client for the unauthenticated Primo VE endpoint
  (`/primaws/rest/pub/pnxs`, CLIC/MnPALS view) plus record normalization.
  Defaults to scope `MyInstitution` (UST's own records only); the blended
  Central Discovery Index scope is opt-in pending license review.
- `app.py` — Starlette app combining the landing page (`/`), a demo API
  (`/api/search`), and the MCP endpoint (`/mcp`).

No credentials, no database, no stored queries.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py          # http://localhost:8080  (MCP endpoint at /mcp)
```

## Deploy

Mirrors the sep-copyediting-assistant recipe: Google Cloud Run, deployed on
push to `main` via GitHub Actions + Workload Identity Federation
(`.github/workflows/deploy.yml`). Manual deploy:

```bash
gcloud run deploy ust-primo-mcp --source . --region us-central1 --allow-unauthenticated
```

## Connect to Claude

Claude → Settings → Connectors → Add custom connector → paste
`https://<service-url>/mcp`. No authentication (the underlying catalog search
is already public).

## Status

Proof of concept by Tom Feeney (thomas.feeney@stthomas.edu), May–June 2026,
for discussion with UST Libraries & ITS. Not an official library service.
