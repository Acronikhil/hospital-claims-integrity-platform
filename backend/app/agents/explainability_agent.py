"""Explainability Agent.

Builds a structured, evidence-backed case summary from the raw findings -
an overview narrative, the risk factors driving the score, the evidence
sources behind them, and a recommendation. Templated from structured
findings rather than freeform generation, so every sentence traces back to
a concrete finding already stored in the graph.
"""

TARIFF_FINDING_TYPES = {"tariff_variance", "not_covered", "unmapped_ambiguous"}
POLICY_FINDING_TYPES = {"sum_insured_exceeded", "room_rent_limit_exceeded"}


def build_summary(
    claim_id: str,
    hospital_name: str,
    patient_name: str,
    procedure: str,
    risk_level: str,
    potential_leakage: float,
    findings: list[dict],
    tariff_reference_available: bool,
    settlement: dict,
    policy_summary: dict,
) -> dict:
    tariff_findings = [f for f in findings if f["type"] in TARIFF_FINDING_TYPES]
    duplicate_findings = [f for f in findings if f["type"] == "duplicate_billing"]
    policy_findings = [f for f in findings if f["type"] in POLICY_FINDING_TYPES]

    if not findings:
        tariff_clause = "the hospital's tariff catalog and " if tariff_reference_available else ""
        overview = (
            f"The claim for {patient_name} at {hospital_name} for {procedure} was investigated "
            f"against {tariff_clause}the claim's own bill items. Every line item matched cleanly "
            f"within its contracted rate, with no duplicate billing or policy issues detected."
        )
        if not tariff_reference_available:
            overview += (
                " Note: no tariff catalog exists in the knowledge graph for this hospital, so tariff "
                "matching could not be run - only duplicate billing was checked."
            )
        else:
            overview += " This claim is recommended for standard processing."
    else:
        parts = [
            f"The claim for {patient_name} at {hospital_name} for {procedure} was flagged "
            f"{risk_level} risk, with a total potential leakage of ₹{potential_leakage:,.0f} "
            f"across {len(findings)} finding(s)."
        ]
        if tariff_findings:
            tariff_total = sum(f["variance"] or 0 for f in tariff_findings)
            parts.append(
                f"{len(tariff_findings)} line item(s) had a tariff-matching issue (over-rate, not "
                f"covered, or ambiguous match) worth a combined ₹{tariff_total:,.0f}."
            )
        if duplicate_findings:
            dup_total = sum(f["variance"] or 0 for f in duplicate_findings)
            parts.append(
                f"{len(duplicate_findings)} instance(s) of potential duplicate billing were identified, "
                f"worth ₹{dup_total:,.0f}."
            )
        if policy_findings:
            policy_total = sum(f["variance"] or 0 for f in policy_findings)
            parts.append(
                f"{len(policy_findings)} policy compliance issue(s) were found (sum insured / room rent "
                f"sub-limit), worth ₹{policy_total:,.0f}."
            )
        if not tariff_reference_available:
            parts.append(
                "No tariff catalog exists for this hospital, so tariff matching was skipped - only "
                "duplicate billing was checked."
            )
        parts.append(
            "Every finding below is backed by the claim's own bill items, the hospital tariff catalog, "
            "and/or the policy master as stored in the knowledge graph."
        )
        overview = " ".join(parts)

    overview += (
        f" System-recommended settlement: ₹{settlement['recommendedSettlementAmount']:,.0f} "
        f"(of ₹{settlement['claimedAmount']:,.0f} claimed)"
    )
    if settlement["sumInsuredCapApplied"]:
        overview += ", capped at the policy's sum insured"
    if policy_summary.get("policyAvailable") and settlement["copayAmount"] > 0:
        overview += (
            f", with a ₹{settlement['copayAmount']:,.0f} co-pay "
            f"({policy_summary['copayPercentage']:.0f}%) leaving ₹{settlement['insurerPayableAmount']:,.0f} payable"
        )
    overview += "."

    risk_factors = [
        {
            "label": finding["description"],
            "detail": (
                f"₹{finding['variance']:,.0f} potential impact · {finding['confidence']}% confidence"
                if finding.get("variance")
                else f"{finding['confidence']}% confidence"
            ),
        }
        for finding in findings
    ]

    if not findings:
        recommendation = "Recommended for standard processing - no adjudicator review required."
    elif risk_level == "HIGH":
        recommendation = "Escalate to a human adjudicator for review before settlement."
    else:
        recommendation = "Route to a human adjudicator for a standard review pass."

    evidence_sources = sorted({f["source"] for f in findings})

    return {
        "overview": overview,
        "riskFactors": risk_factors,
        "evidenceSources": evidence_sources,
        "recommendation": recommendation,
        "tariffReferenceAvailable": tariff_reference_available,
    }
