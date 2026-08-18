from typing import Optional
from pydantic import BaseModel, Field


class BillItemIn(BaseModel):
    description: str
    itemType: str
    amount: float
    quantity: int = 1


class ClaimIn(BaseModel):
    patientId: str
    patientName: str
    policyNumber: str
    hospitalId: str
    doctorName: str
    diagnosis: str
    procedure: str
    admissionDate: str
    dischargeDate: str
    lengthOfStayDays: int
    billItems: list[BillItemIn] = Field(default_factory=list)


class Finding(BaseModel):
    findingId: str
    agent: str
    type: str
    description: str
    reason: str
    billedAmount: Optional[float] = None
    allowedAmount: Optional[float] = None
    variance: Optional[float] = None
    confidence: int
    recommendedAction: str
    source: str


class RiskFactor(BaseModel):
    label: str
    detail: str


class CaseSummary(BaseModel):
    overview: str
    riskFactors: list[RiskFactor] = Field(default_factory=list)
    evidenceSources: list[str] = Field(default_factory=list)
    recommendation: str
    tariffReferenceAvailable: bool = True


class PipelineStep(BaseModel):
    step: str
    agent: str
    status: str  # success | warning | skipped | info
    summary: str
    detail: Optional[str] = None
    durationMs: Optional[int] = None


class ClaimReport(BaseModel):
    claimId: str
    riskLevel: str
    potentialLeakage: float
    findings: list[Finding]
    summary: CaseSummary
    pipeline: list[PipelineStep] = Field(default_factory=list)
    status: str
    sourceType: str = "MANUAL"
    sourceFileNames: list[str] = Field(default_factory=list)


class ExtractedBillItem(BaseModel):
    description: str
    itemType: str
    amount: float
    quantity: int = 1


class ExtractedClaim(BaseModel):
    patientId: Optional[str] = None
    patientName: str
    policyNumber: str
    hospitalName: str
    doctorName: str
    diagnosis: str
    procedure: str
    admissionDate: str
    dischargeDate: str
    lengthOfStayDays: int
    billItems: list[ExtractedBillItem] = Field(default_factory=list)


class ClaimSummary(BaseModel):
    claimId: str
    patientName: Optional[str] = None
    hospitalName: Optional[str] = None
    procedure: Optional[str] = None
    claimedAmount: Optional[float] = None
    riskLevel: Optional[str] = None
    potentialLeakage: Optional[float] = None
    status: Optional[str] = None
    createdAt: Optional[str] = None


class ClaimDetail(BaseModel):
    claim: dict
    patient: Optional[dict] = None
    hospital: Optional[dict] = None
    doctor: Optional[dict] = None
    diagnosis: Optional[dict] = None
    procedure: Optional[dict] = None
    billItems: list[dict] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)


class DecisionIn(BaseModel):
    decision: str  # APPROVED | QUERIED | DEDUCTED | ESCALATED
    note: Optional[str] = None
