# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hospital Claims Integrity Platform — Phase 1 MVP. A rule/graph-based (no LLM, no external AI API)
claims investigation pipeline: PDF bills are extracted, written into a Neo4j knowledge graph,
fuzzy-matched against a tariff catalog, checked for duplicates and policy compliance, then scored
into a risk/settlement recommendation. See [README.md](README.md) for the full pipeline
description, tariff-matching thresholds, and demo policy numbers — read it before making changes
to any agent.

## Commands

Run everything (frontend, backend, Neo4j) via Docker:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173 · Backend docs: http://localhost:8000/docs · Neo4j Browser: http://localhost:7474 (`neo4j` / `claims_password`)
- Source is bind-mounted with `--reload` (backend) and polling (frontend), so edits apply live — only rebuild after changing `requirements.txt`/`package.json`/Dockerfiles.

Backend only, without Docker (requires a running Neo4j — see README "Run locally without Docker"):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend only:

```bash
cd frontend
npm install
npm run dev      # dev server
npm run build     # production build
npm run preview    # preview a build
```

There is no test suite and no lint script configured in either package yet — don't assume `pytest`
or `npm run lint` exist.

## Architecture

**Backend (`backend/app/`)** — FastAPI. Every Cypher query in the app lives in one module,
`graph_repo.py`; nothing else calls the Neo4j driver directly. `db.py` owns the driver singleton
and schema constraints (`init_constraints()`, run on startup alongside `seed_data.seed()` in
`main.py`).

The claims pipeline is a chain of stateless agent modules under `agents/`, coordinated by
`agents/orchestrator.py`:

```
document_agent -> graph_repo.create_claim_graph -> tariff_agent -> duplicate_agent
  -> policy_agent -> risk_engine -> settlement_engine -> explainability_agent
```

Each agent takes/returns plain data (not graph objects) and the orchestrator records every step as
a pipeline trace entry (surfaced in the UI's "Investigation Pipeline"). When adding a new agent,
follow this same pattern: pure function, orchestrator wires it in, results get logged to the trace
and written back to the graph via a `graph_repo` function — don't query Neo4j directly from an
agent.

**Graph data has two lifecycles** — see README's "What's static vs. dynamic in the graph" section
before assuming tariff/policy data can be changed at runtime: `Hospital`, `TariffItem`,
`Procedure`, `Policy` nodes are static, hardcoded in `seed_data.py` and re-applied via idempotent
`MERGE` on every startup (no admin endpoint to change them). `Claim`, `Patient`, `Doctor`,
`BillItem`, `Finding` nodes are created live per upload.

**Frontend (`frontend/src/`)** — plain React + Vite, no state management library. `api.js` is the
single Axios client; `pages/` (Dashboard, UploadClaim, ClaimDetail) call it directly and pass data
down to presentational `components/`.

**No LLM/external AI API anywhere in this pipeline** — extraction is regex + Tesseract OCR
(`document_agent.py`), tariff matching is `rapidfuzz` string similarity (`tariff_agent.py`). If
extraction proves too brittle against real bill formats, the intended extension point is swapping
in an LLM-based implementation behind the same `extract_claim_from_documents(files) ->
ExtractedClaim` interface, without touching the rest of the pipeline.
