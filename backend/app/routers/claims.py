from fastapi import APIRouter, File, HTTPException, UploadFile

from app import graph_repo
from app.agents.orchestrator import process_claim, process_claim_from_documents
from app.schemas import ClaimDetail, ClaimIn, ClaimReport, ClaimSummary, DecisionIn

router = APIRouter(prefix="/api/claims", tags=["claims"])

VALID_DECISIONS = {"APPROVED", "QUERIED", "DEDUCTED", "ESCALATED"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024
MAX_FILES = 10


@router.post("", response_model=ClaimReport)
def submit_claim(claim: ClaimIn):
    return process_claim(claim)


@router.post("/upload", response_model=ClaimReport)
async def upload_claim(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Attach at least one PDF document.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Attach at most {MAX_FILES} documents per claim.")

    file_data: list[tuple[str, bytes]] = []
    total_size = 0

    for upload in files:
        if upload.content_type != "application/pdf" and not (upload.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' is not a PDF. Only PDF files are supported.")

        pdf_bytes = await upload.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' is empty.")
        if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' exceeds the 20 MB per-file limit.")

        total_size += len(pdf_bytes)
        if total_size > MAX_TOTAL_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Combined document size exceeds the 30 MB upload limit.")

        file_data.append((upload.filename or "document.pdf", pdf_bytes))

    try:
        return process_claim_from_documents(file_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[ClaimSummary])
def get_claims():
    return graph_repo.list_claims()


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: str):
    detail = graph_repo.get_claim_detail(claim_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return detail


@router.post("/{claim_id}/decision")
def decide_claim(claim_id: str, decision: DecisionIn):
    if decision.decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {sorted(VALID_DECISIONS)}")
    if graph_repo.get_claim_detail(claim_id) is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    graph_repo.update_claim_decision(claim_id, decision.decision, decision.note)
    return {"claimId": claim_id, "status": decision.decision}
