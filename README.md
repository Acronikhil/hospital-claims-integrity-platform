# Hospital Claims Integrity Platform — Phase 1 MVP

An AI-agent-style claims investigation prototype built on a Neo4j knowledge graph.
Given one or more documents for a claim (final bill, pre-authorization form, discharge summary,
prescriptions, investigation reports — all PDF), the system:

1. **Extracts** the claim via a **Document Intelligence Agent** — reads all uploaded documents
   together using `pdfplumber` (text and tables), with a local Tesseract OCR fallback for
   scanned/photographed pages, and reconciles them into one structured
   patient/hospital/procedure/bill-item record (bill items are only ever drawn from an actual
   bill table or amount-shaped line, never invented). Fully local — no external AI API or key.
2. Writes the claim into a Neo4j knowledge graph, connecting
   `Patient → Policy → Claim → Hospital → Doctor → Diagnosis → Procedure → BillItem → Tariff`.
3. Runs a **Tariff Intelligence Agent** that compares each billed line item against the
   hospital's contracted tariff (stored as graph nodes, never invented).
4. Runs a **Duplicate Billing Agent** that flags repeated line items on the same claim.
5. Aggregates findings into a **Risk Assessment** (LOW / MEDIUM / HIGH + potential leakage ₹).
6. Produces an **Evidence-Backed Case Summary** (Explainability Agent) — every finding cites
   its source (tariff master node / bill item node) instead of a black-box score.
7. Records every step above as an **Investigation Pipeline** trace — like a CI run's checks list
   — so a reviewer can see exactly what each agent did and drill into its raw output.
8. Presents everything on a **Claims Workbench** dashboard where a human adjudicator can
   Approve / Query / Deduct / Escalate.

This is the Phase 1 MVP scope from the design doc — Tariff + Duplicate agents only, rule/graph-based
reasoning throughout, including document extraction (no LLM/external AI API anywhere in this
pipeline). Clinical, Historical Pattern, Provider Behaviour agents and the query-generation
feedback loop are intentionally out of scope for this pass and can be layered on the same graph
model later.

## Tech stack

- **Frontend:** React (Vite) + React Router + Axios
- **Backend:** FastAPI + neo4j Python driver + pdfplumber + pytesseract (Tesseract OCR)
- **Knowledge Graph:** Neo4j

No API keys or external services are required — everything runs locally.

## Document extraction: how it works, and its limits

`backend/app/agents/document_agent.py` extracts fields with labeled regex patterns (`Patient
Name:`, `Policy Number:`, `Admission Date:`, ...) and pulls bill line items from PDF tables first,
falling back to lines shaped like `Description ... Amount` when no table is detected. Pages with no
extractable text layer (scanned/photographed documents) are rasterized and OCR'd with Tesseract.

Because there's no AI model doing the reading, extraction quality depends on the document
following a reasonably consistent layout:

- Fields work best as `Label: Value` (e.g. `Patient Name: Jane Doe`, `Admission Date: 10/08/2026`).
- Bill items work best as a table with a header row containing something like
  "Description"/"Particulars" and "Amount"/"Charges".
- Dates are parsed as `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, or `YYYY-MM-DD`.
- Lines containing "total", "balance", "subtotal", "advance", "discount", "gst", or "tax" are
  excluded from bill items so totals/tax rows aren't mistaken for line items.

If a field can't be found on any uploaded document, the claim still processes with an obvious
placeholder (`"Unknown Hospital"`, `"Not specified"`, etc.) rather than failing outright — the
placeholder is visible on the claim detail page and in the Document Extraction pipeline step's raw
output, so a reviewer immediately sees what wasn't read correctly rather than acting on a silent
guess. At least one bill item must be found or the upload is rejected with a 422.

If your real bills use a substantially different layout, extend the regex patterns/keywords in
`document_agent.py` (`FIELD_PATTERNS`, `ITEM_TYPE_KEYWORDS`) to match your format.

## Run everything with Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (user `neo4j`, password `claims_password`)

Source is bind-mounted for both services (`--reload` on the backend, Vite dev server with polling
on the frontend — Windows/Docker Desktop bind mounts don't reliably forward filesystem events, so
`vite.config.js` sets `watch.usePolling`), so further edits apply without rebuilding the images —
only rebuild after changing `requirements.txt` / `package.json` or the Dockerfiles.

The backend seeds two demo hospitals (ABC Hospital, XYZ Multispecialty Hospital) with tariffs
for **Cataract Surgery** and **Cardiac Bypass Surgery** on startup. A PDF bill for a hospital
name that doesn't match a seeded one still processes — an ad-hoc `Hospital` node is created and
the case summary notes that tariff checks were skipped for it (duplicate billing is still
checked).

## Run locally without Docker

### 1. Start Neo4j

Easiest via Docker just for the database:

```bash
docker run -d --name claims-neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/claims_password neo4j:5.24-community
```

Or point `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` at a Neo4j Desktop / Aura instance.

### 2. Backend

Requires the Tesseract OCR binary on PATH for the scanned-document fallback (`apt-get install
tesseract-ocr` on Debian/Ubuntu, `choco install tesseract` on Windows, `brew install tesseract` on
macOS). Extraction of text-layer PDFs still works fine without it.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env      # edit Neo4j creds if needed
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000 (docs at `/docs`).

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend runs at http://localhost:5173.

## Try it out

1. Open the frontend, click **Upload Claim**, and drop in one or more claim document PDFs (up to
   10 files, 20 MB each) — for **ABC Hospital** / **Cataract Surgery** claims, try a bill with:
   - `Patient Name:`, `Policy Number:`, `Admission Date:`, `Discharge Date:` labeled fields
   - A line-item table with a "Description"/"Amount" header, including:
     - OT Charges — 40,000 (allowed: ₹25,000 → tariff variance flagged)
     - Room Charges — 8,000
     - The same investigation billed twice at the same amount (e.g. MRI Brain — 8,000, twice →
       duplicate billing flagged)

   You can attach just the bill, or the bill alongside a pre-auth form / discharge summary — the
   Document Intelligence Agent merges fields across all of them (first document to have a labeled
   match for a field wins).
2. Submit. You'll land on the claim detail page with the **Investigation Pipeline** (what each
   agent did — expand "Document Extraction" to see exactly what was read off the PDF), a risk
   level, potential leakage, an evidence-backed **Case Summary** with a financial breakdown,
   individual findings, and Approve/Query/Deduct/Escalate actions.
3. Go back to the dashboard to see it listed with its risk badge and leakage figure.

`POST /api/claims` (structured JSON, documented at `/docs`) still exists for programmatic/testing
use — it runs the same pipeline without the PDF extraction step — but the UI now only exposes the
upload flow, since claim data arrives as PDFs in practice.

## Project layout

```
backend/
  app/
    main.py               FastAPI app, CORS, startup seeding
    db.py                  Neo4j driver + schema constraints
    schemas.py              Pydantic request/response models
    graph_repo.py           All Cypher queries (the knowledge graph layer)
    seed_data.py             Demo hospitals/procedures/tariffs
    constants.py              Shared bill item type list
    agents/
      document_agent.py         PDF -> structured claim (pdfplumber + Tesseract OCR, fully local)
      tariff_agent.py            Tariff variance detection
      duplicate_agent.py         Duplicate line-item detection
      risk_engine.py              Deterministic risk scoring
      explainability_agent.py     Evidence-backed case summary
      orchestrator.py             Coordinates the above per claim, builds the pipeline trace
    routers/
      claims.py    POST /api/claims, POST /api/claims/upload, GET /api/claims, GET /api/claims/{id}, decision endpoint
      reference.py  hospitals/procedures/item-types (used by /docs and programmatic clients)
frontend/
  src/
    pages/       Dashboard, UploadClaim, ClaimDetail
    components/  RiskBadge, FindingCard, CaseSummary, PipelineView
    api.js       Axios client
```

## Extending beyond this MVP

The graph model already has the hooks the design doc describes for later phases:

- **Historical Pattern Agent:** query `Hospital-HAS_TARIFF->Tariff<-HAS_TARIFF-Hospital` siblings
  and `(Hospital)<-[:SUBMITTED_BY]-(Claim)-[:HAS_PROCEDURE]->(Procedure)` to compare a new claim
  against a hospital's historical average for the same procedure.
- **Clinical Intelligence Agent:** add `ClinicalGuideline` nodes with `expectedLOS`, link them to
  `Procedure` via `HAS_GUIDELINE`, and compare against `Claim.lengthOfStayDays`.
- **Unbundling Agent:** add `Package` nodes with `INCLUDES` relationships to expected bill item
  types, compare against what was actually billed.
- **Document node tracking:** the graph doesn't yet create `Document` nodes per uploaded file
  (only `sourceFileNames` on the `Claim`); add `(Claim)-[:HAS_DOCUMENT]->(Document)` if you need
  to trace individual source files (e.g. for the query-generation feedback loop).
- **Higher-accuracy extraction:** if the rule-based extraction proves too brittle against real
  bill formats, an LLM-based extraction step (e.g. via the Claude or another provider's API) can
  be swapped in behind the same `extract_claim_from_documents(files) -> ExtractedClaim` interface
  in `document_agent.py` without touching the rest of the pipeline.
