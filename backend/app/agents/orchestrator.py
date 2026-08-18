"""Claim Orchestrator Agent.

Coordinates the specialist agents for a single claim: creates the claim's
subgraph in Neo4j, runs the Document, Tariff and Duplicate agents against
it, feeds their findings into the Risk Engine, and produces the final
explainability report. Every step's outcome is recorded as a pipeline
trace so a reviewer can see exactly what each agent did, similar to a
CI pipeline's per-step checks.
"""
import re
import time
import uuid

from app import graph_repo
from app.agents import document_agent, duplicate_agent, explainability_agent, risk_engine, tariff_agent
from app.schemas import BillItemIn, CaseSummary, ClaimIn, ClaimReport, PipelineStep


def _slugify_hospital_id(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return f"H-{slug[:40]}-{uuid.uuid4().hex[:4].upper()}"


def _resolve_hospital(hospital_name: str) -> str:
    match = graph_repo.find_hospital_by_name(hospital_name)
    if match:
        return match["hospitalId"]

    hospital_id = _slugify_hospital_id(hospital_name)
    graph_repo.create_hospital(hospital_id, hospital_name)
    return hospital_id


def process_claim_from_documents(files: list[tuple[str, bytes]]) -> ClaimReport:
    """files: list of (filename, pdf_bytes) tuples - all documents for one claim."""
    pipeline: list[PipelineStep] = []
    filenames = [name for name, _ in files]

    start = time.perf_counter()
    extracted = document_agent.extract_claim_from_documents(files)
    duration_ms = int((time.perf_counter() - start) * 1000)

    if not extracted.billItems:
        raise ValueError("No bill items could be extracted from these documents.")

    source_desc = filenames[0] if len(filenames) == 1 else f"{len(filenames)} documents ({', '.join(filenames)})"
    pipeline.append(
        PipelineStep(
            step="Document Extraction",
            agent="Document Intelligence Agent",
            status="success",
            summary=(
                f"Extracted {extracted.patientName} / {extracted.hospitalName} / {extracted.procedure} "
                f"with {len(extracted.billItems)} bill item(s) from {source_desc} using {document_agent.METHOD}."
            ),
            detail=extracted.model_dump_json(indent=2),
            durationMs=duration_ms,
        )
    )

    hospital_id = _resolve_hospital(extracted.hospitalName)
    patient_id = extracted.patientId or f"PT-{uuid.uuid4().hex[:8].upper()}"

    claim = ClaimIn(
        patientId=patient_id,
        patientName=extracted.patientName,
        policyNumber=extracted.policyNumber,
        hospitalId=hospital_id,
        doctorName=extracted.doctorName,
        diagnosis=extracted.diagnosis,
        procedure=extracted.procedure,
        admissionDate=extracted.admissionDate,
        dischargeDate=extracted.dischargeDate,
        lengthOfStayDays=extracted.lengthOfStayDays,
        billItems=[
            BillItemIn(
                description=item.description,
                itemType=item.itemType,
                amount=item.amount,
                quantity=item.quantity,
            )
            for item in extracted.billItems
        ],
    )

    return process_claim(claim, source_type="PDF_UPLOAD", source_file_names=filenames, pipeline=pipeline)


def process_claim(
    claim: ClaimIn,
    source_type: str = "MANUAL",
    source_file_names: list[str] | None = None,
    pipeline: list[PipelineStep] | None = None,
) -> ClaimReport:
    pipeline = list(pipeline or [])
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    start = time.perf_counter()
    bill_items = graph_repo.create_claim_graph(claim_id, claim, source_type, source_file_names)
    pipeline.append(
        PipelineStep(
            step="Knowledge Graph Write",
            agent="Claim Orchestrator Agent",
            status="info",
            summary=(
                f"Wrote {claim_id} into Neo4j: Patient → Policy → Claim → Hospital → Doctor → Diagnosis "
                f"→ Procedure → {len(bill_items)} BillItem node(s)."
            ),
            durationMs=int((time.perf_counter() - start) * 1000),
        )
    )

    start = time.perf_counter()
    tariff_findings, tariff_reference_available = tariff_agent.run(
        claim_id, claim.hospitalId, claim.procedure, bill_items
    )
    tariff_duration = int((time.perf_counter() - start) * 1000)
    if not tariff_reference_available:
        pipeline.append(
            PipelineStep(
                step="Tariff Check",
                agent="Tariff Intelligence Agent",
                status="skipped",
                summary="No contracted tariff reference data exists for this hospital/procedure - tariff check skipped.",
                durationMs=tariff_duration,
            )
        )
    elif tariff_findings:
        pipeline.append(
            PipelineStep(
                step="Tariff Check",
                agent="Tariff Intelligence Agent",
                status="warning",
                summary=f"Flagged {len(tariff_findings)} line item(s) exceeding the contracted tariff.",
                durationMs=tariff_duration,
            )
        )
    else:
        pipeline.append(
            PipelineStep(
                step="Tariff Check",
                agent="Tariff Intelligence Agent",
                status="success",
                summary="All billed line items are within the hospital's contracted tariff.",
                durationMs=tariff_duration,
            )
        )

    start = time.perf_counter()
    duplicate_findings = duplicate_agent.run(claim_id, bill_items)
    duplicate_duration = int((time.perf_counter() - start) * 1000)
    if duplicate_findings:
        pipeline.append(
            PipelineStep(
                step="Duplicate Check",
                agent="Duplicate Billing Agent",
                status="warning",
                summary=f"Flagged {len(duplicate_findings)} potential duplicate line item group(s).",
                durationMs=duplicate_duration,
            )
        )
    else:
        pipeline.append(
            PipelineStep(
                step="Duplicate Check",
                agent="Duplicate Billing Agent",
                status="success",
                summary="No duplicate line items detected among the billed items.",
                durationMs=duplicate_duration,
            )
        )

    findings = tariff_findings + duplicate_findings

    start = time.perf_counter()
    risk_level, potential_leakage = risk_engine.assess(findings)
    pipeline.append(
        PipelineStep(
            step="Risk Assessment",
            agent="Risk Assessment Engine",
            status="warning" if risk_level == "HIGH" else ("info" if risk_level == "MEDIUM" else "success"),
            summary=(
                f"Aggregated {len(findings)} finding(s) → {risk_level} risk, "
                f"₹{potential_leakage:,.0f} potential leakage."
            ),
            durationMs=int((time.perf_counter() - start) * 1000),
        )
    )

    hospitals = {h["hospitalId"]: h["name"] for h in graph_repo.list_hospitals()}
    hospital_name = hospitals.get(claim.hospitalId, claim.hospitalId)

    start = time.perf_counter()
    summary_dict = explainability_agent.build_summary(
        claim_id=claim_id,
        hospital_name=hospital_name,
        patient_name=claim.patientName,
        procedure=claim.procedure,
        risk_level=risk_level,
        potential_leakage=potential_leakage,
        findings=findings,
        tariff_reference_available=tariff_reference_available,
    )
    summary = CaseSummary(**summary_dict)
    pipeline.append(
        PipelineStep(
            step="Case Summary",
            agent="Explainability Agent",
            status="success",
            summary="Built the evidence-backed case summary and recommendation.",
            durationMs=int((time.perf_counter() - start) * 1000),
        )
    )

    status = "HIGH RISK - PENDING REVIEW" if risk_level == "HIGH" else (
        "MEDIUM RISK - PENDING REVIEW" if risk_level == "MEDIUM" else "PENDING REVIEW"
    )

    pipeline_json = "[" + ",".join(step.model_dump_json() for step in pipeline) + "]"
    graph_repo.update_claim_result(
        claim_id, risk_level, potential_leakage, summary.model_dump_json(), pipeline_json, status
    )

    return ClaimReport(
        claimId=claim_id,
        riskLevel=risk_level,
        potentialLeakage=potential_leakage,
        findings=findings,
        summary=summary,
        pipeline=pipeline,
        status=status,
        sourceType=source_type,
        sourceFileNames=source_file_names or [],
    )
