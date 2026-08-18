"""Explainability Agent.

Builds a structured, evidence-backed case summary from the raw findings -
an overview narrative, the risk factors driving the score, the evidence
sources behind them, and a recommendation. Templated from structured
findings rather than freeform generation, so every sentence traces back to
a concrete finding already stored in the graph.
"""


def build_summary(
    claim_id: str,
    hospital_name: str,
    patient_name: str,
    procedure: str,
    risk_level: str,
    potential_leakage: float,
    findings: list[dict],
    tariff_reference_available: bool,
) -> dict:
    tariff_findings = [f for f in findings if f["type"] == "tariff_variance"]
    duplicate_findings = [f for f in findings if f["type"] == "duplicate_billing"]

    if not findings:
        tariff_clause = "the hospital's contracted tariff and " if tariff_reference_available else ""
        overview = (
            f"The claim for {patient_name} at {hospital_name} for {procedure} was investigated "
            f"against {tariff_clause}the claim's own bill items. No tariff variances or duplicate "
            f"billing were detected."
        )
        if not tariff_reference_available:
            overview += (
                " Note: no contracted tariff reference data exists in the knowledge graph for this "
                "hospital/procedure combination, so tariff checks could not be run - only duplicate "
                "billing was checked."
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
                f"{len(tariff_findings)} line item(s) exceeded the hospital's contracted tariff by a "
                f"combined ₹{tariff_total:,.0f}."
            )
        if duplicate_findings:
            dup_total = sum(f["variance"] or 0 for f in duplicate_findings)
            parts.append(
                f"{len(duplicate_findings)} instance(s) of potential duplicate billing were identified, "
                f"worth ₹{dup_total:,.0f}."
            )
        if not tariff_reference_available:
            parts.append(
                "No contracted tariff reference data exists for this hospital/procedure combination, "
                "so tariff checks were skipped - only duplicate billing was checked."
            )
        parts.append(
            "Every finding below is backed by the claim's own bill items and/or the hospital tariff "
            "master as stored in the knowledge graph."
        )
        overview = " ".join(parts)

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
