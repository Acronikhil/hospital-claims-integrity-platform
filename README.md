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
   `Patient → Policy → Claim → Hospital → Doctor → Diagnosis → Procedure → BillItem → TariffItem`.
3. Runs a **Tariff Matching Agent** that fuzzy-matches every billed line item against the
   hospital's tariff catalog (`rapidfuzz`, local — no external AI API) and classifies each one:
   **Matched & Within Rate**, **Matched & Over Rate**, **Matched & Under Rate**, **Not Covered**,
   **Unmapped/Ambiguous**, or **Duplicate/Quantity Discrepancy** — the graph-matching classification
   scheme from the claims-integrity design doc.
4. Runs a **Duplicate Billing Agent** that flags repeated line items on the same claim.
5. Runs a **Policy Compliance Agent** that compares the claim against the patient's policy terms
   (sum insured cap, room rent daily sub-limit), stored as a Policy Master in the graph.
6. Aggregates findings into a **Risk Assessment** (LOW / MEDIUM / HIGH + potential leakage ₹) and
   a **Settlement Engine** that computes a system-recommended settlement amount — distinct from
   simply approving up to the pre-authorized ceiling — capped at the sum insured and net of co-pay.
7. Produces an **Evidence-Backed Case Summary** (Explainability Agent) — every finding cites
   its source (tariff catalog entry / bill item / policy master) instead of a black-box score.
8. Records every step above as an **Investigation Pipeline** trace — like a CI run's checks list
   — so a reviewer can see exactly what each agent did and drill into its raw output.
9. Presents everything on a **Claims Workbench** dashboard where a human adjudicator can
   Approve / Query / Deduct / Escalate.

This is the Phase 1 MVP scope from the design doc — Tariff Matching, Duplicate, and Policy
Compliance agents, rule/graph-based reasoning throughout, including document extraction (no
LLM/external AI API anywhere in this pipeline). Package/bundle tariff modeling (a tariff "package"
expanding into component line items), rate validity periods, Historical Pattern, Clinical, and
Provider Behaviour agents, and the query-generation feedback loop are intentionally out of scope
for this pass and can be layered on the same graph model later.

## Tech stack

- **Frontend:** React (Vite) + React Router + Axios
- **Backend:** FastAPI + neo4j Python driver + pdfplumber + pytesseract (Tesseract OCR)
- **Knowledge Graph:** Neo4j

No API keys or external services are required — everything runs locally.

## What's static vs. dynamic in the graph

The Neo4j graph holds two kinds of data with very different lifecycles:

- **Static reference data — Hospital, TariffItem, Procedure, Policy nodes.** These come entirely
  from the hardcoded Python literals in `seed_data.py` and are re-applied via idempotent `MERGE`
  every time the backend starts (`main.py` startup hook) — the values never change at runtime and
  there's no admin endpoint or ETL job to update them; `reference.py` only exposes read-only GETs.
  Search against this data (the tariff-matching fuzzy lookup) always runs against the same fixed
  catalog.
- **Dynamic transactional data — Claim, Patient, Doctor, Diagnosis, BillItem, Finding nodes.**
  These are created live, per request, from uploaded PDF bills via the Document Intelligence Agent
  and written to the graph through `graph_repo.create_claim_graph`. A hospital name that doesn't
  match a seeded one gets an ad-hoc `Hospital` node created on the fly (see below), but it inherits
  no tariff catalog, so tariff matching is skipped for it.

In short: claims flow into the graph dynamically, but they're matched against a static, hardcoded
demo tariff/policy dataset — see "Extending beyond this MVP" for what real tariff ingestion would
require.

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

## Tariff matching: how it works, and its thresholds

`backend/app/agents/tariff_agent.py` fuzzy-matches each bill item's free-text description against
the hospital's tariff catalog (`TariffItem` nodes, one per `(hospital, procedure, category)` —
seeded in `seed_data.py`) using `rapidfuzz`'s `token_set_ratio`, scoped first to the claim's
procedure (falling back to the hospital's full catalog if nothing matches there). Confidence
score decides the classification:

- **≥ 70%** — confident match; then billed vs. tariff rate decides **Within / Over / Under Rate**.
- **40–69%** — **Unmapped/Ambiguous**: closest guess is shown, but needs manual review.
- **< 40%** — **Not Covered**: nothing in the catalog resembles the item.

Items also flagged as duplicates by the Duplicate Billing Agent are overlaid as
**Duplicate/Quantity Discrepancy** in the classification breakdown, taking priority for review
regardless of their tariff match. Tune `CONFIDENT_MATCH_THRESHOLD` / `NOT_COVERED_THRESHOLD` in
`tariff_agent.py` if your catalog descriptions need a different sensitivity.

The **Settlement Engine** (`settlement_engine.py`) then aggregates: Within/Under-Rate items count
at their billed amount, Over-Rate items are capped at the tariff rate, Not Covered/Ambiguous/
Duplicate amounts are withheld pending review, duplicate leakage is subtracted, and the total is
capped at the policy's sum insured (if available) before co-pay is applied — producing the
system-recommended settlement shown on the claim detail page, distinct from just approving up to
a pre-authorized ceiling.

## Policy comparison: demo policies

`backend/app/agents/policy_agent.py` checks the claim against a `Policy` node's sum insured and
room rent daily sub-limit. Real hospital bills don't carry this data (it lives in the insurer's
own policy master), so two representative demo policies are seeded on startup — use one of these
exact policy numbers in a test document's `Policy Number:` field to exercise the check:

| Policy Number | Plan | Sum Insured | Room Rent/Day | Co-pay |
|---|---|---|---|---|
| `POL-STANDARD-001` | Health Standard Plan | ₹5,00,000 | ₹5,000 | 10% |
| `POL-PREMIUM-001` | Health Premium Plan | ₹20,00,000 | ₹15,000 | 0% |

An unrecognized policy number still processes the claim — the Policy Compliance Agent reports "no
policy reference data available" and skips those checks, same pattern as an unmatched hospital.

Note: many real policies apply a *proportionate deduction* across all associated charges (OT,
surgeon, nursing) when the room category exceeds the eligible limit, not just a cap on the room
charge itself. That cascading rule is not implemented here — the room rent finding flags and caps
only the room charges; extend `policy_agent.py` if you need the full proportionate-deduction logic.

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

The backend seeds two demo hospitals (ABC Hospital, XYZ Multispecialty Hospital) with a tariff
catalog for **Cataract Surgery** and **Cardiac Bypass Surgery**, and two demo policies
(`POL-STANDARD-001`, `POL-PREMIUM-001` — see below) on startup. A PDF bill for a hospital name
that doesn't match a seeded one still processes — an ad-hoc `Hospital` node is created and the
case summary notes that tariff matching was skipped for it (duplicate billing is still checked).

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
   - `Patient Name:`, `Policy Number: POL-STANDARD-001`, `Admission Date:`, `Discharge Date:`
     labeled fields (the policy number exercises the sum insured / room rent checks)
   - A line-item table with a "Description"/"Amount" header, including:
     - OT Charges — 40,000 (tariff: ₹25,000 → Matched & Over Rate)
     - Room Charges — 12,000 over 2 days (tariff: ₹8,000, and ₹6,000/day exceeds the policy's
       ₹5,000/day room rent sub-limit → both a tariff and a policy finding)
     - Surgeon Fee — 20,000 (tariff: ₹20,000 → Matched & Within Rate)
     - The same investigation billed twice at the same amount (e.g. MRI Brain — 8,000, twice →
       Not Covered *and* Duplicate/Quantity Discrepancy, since "MRI Brain" isn't in the Cataract
       Surgery tariff catalog either)

   You can attach just the bill, or the bill alongside a pre-auth form / discharge summary — the
   Document Intelligence Agent merges fields across all of them (first document to have a labeled
   match for a field wins).
2. Submit. You'll land on the claim detail page with a **Settlement & Policy** panel (claimed vs.
   recommended settlement, sum insured/room rent/co-pay), the **Investigation Pipeline** (what each
   agent did — expand "Document Extraction" to see exactly what was read off the PDF), an
   evidence-backed **Case Summary**, the **Tariff Matching Breakdown** table (every bill item, its
   matched tariff entry, confidence score, and classification), individual findings, and
   Approve/Query/Deduct/Escalate actions.
3. Go back to the dashboard to see it listed with its risk badge, potential leakage, and
   recommended settlement figure.

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
    seed_data.py             Demo hospitals/tariff catalog/policies
    constants.py              Shared bill item types + classification status constants
    agents/
      document_agent.py         PDF -> structured claim (pdfplumber + Tesseract OCR, fully local)
      tariff_agent.py            Fuzzy tariff-catalog matching + 6-state classification
      duplicate_agent.py         Duplicate line-item detection
      policy_agent.py             Sum insured / room rent sub-limit checks
      risk_engine.py              Deterministic risk scoring
      settlement_engine.py         Recommended settlement amount calculation
      explainability_agent.py     Evidence-backed case summary
      orchestrator.py             Coordinates the above per claim, builds the pipeline trace
    routers/
      claims.py    POST /api/claims, POST /api/claims/upload, GET /api/claims, GET /api/claims/{id}, decision endpoint
      reference.py  hospitals/procedures/item-types/tariff-catalog (used by /docs and programmatic clients)
frontend/
  src/
    pages/       Dashboard, UploadClaim, ClaimDetail
    components/  RiskBadge, FindingCard, CaseSummary, PipelineView, BillClassificationTable,
                 ClassificationBadge, SettlementPanel
    api.js       Axios client
```

## Extending beyond this MVP

The graph model already has the hooks the design doc describes for later phases:

- **Historical Pattern Agent:** query `Hospital-HAS_TARIFF->Tariff<-HAS_TARIFF-Hospital` siblings
  and `(Hospital)<-[:SUBMITTED_BY]-(Claim)-[:HAS_PROCEDURE]->(Procedure)` to compare a new claim
  against a hospital's historical average for the same procedure.
- **Clinical Intelligence Agent:** add `ClinicalGuideline` nodes with `expectedLOS`, link them to
  `Procedure` via `HAS_GUIDELINE`, and compare against `Claim.lengthOfStayDays`.
- **Unbundling / package agent:** add `Package` nodes with `INCLUDES` relationships from a
  `TariffItem` to the component line items it bundles (e.g. a surgical package including room
  rent + OT + consumables), and detect when a hospital bills the components separately instead of
  the package rate.
- **Proportionate room-rent deduction:** `policy_agent.py` currently only caps the room charge
  itself when it exceeds the sub-limit; extend it to also proportionately reduce associated
  charges (OT/surgeon/nursing) per the common real-world policy rule noted above.
- **Rate validity periods:** `TariffItem` has no effective-date range; add one if tariffs change
  over time and claims need to be matched against the rate that was contracted on the admission
  date.
- **Document node tracking:** the graph doesn't yet create `Document` nodes per uploaded file
  (only `sourceFileNames` on the `Claim`); add `(Claim)-[:HAS_DOCUMENT]->(Document)` if you need
  to trace individual source files (e.g. for the query-generation feedback loop).
- **Higher-accuracy extraction:** if the rule-based extraction proves too brittle against real
  bill formats, an LLM-based extraction step (e.g. via the Claude or another provider's API) can
  be swapped in behind the same `extract_claim_from_documents(files) -> ExtractedClaim` interface
  in `document_agent.py` without touching the rest of the pipeline.
