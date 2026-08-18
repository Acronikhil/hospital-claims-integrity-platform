"""Settlement Engine.

Aggregates the per-item tariff classifications, duplicate findings, and
policy terms into a single system-recommended settlement amount -
distinct from simply approving up to the pre-authorized ceiling, per the
claims-integrity design doc's "recommended settlement amount" goal.
"""
from app.constants import MATCHED_OVER_RATE, MATCHED_UNDER_RATE, MATCHED_WITHIN_RATE


def calculate(
    claimed_amount: float,
    classifications: list[dict],
    duplicate_findings: list[dict],
    policy_summary: dict,
) -> dict:
    gross_recommended = 0.0
    for classification in classifications:
        status = classification["status"]
        if status in (MATCHED_WITHIN_RATE, MATCHED_UNDER_RATE):
            gross_recommended += classification["billedAmount"]
        elif status == MATCHED_OVER_RATE:
            gross_recommended += classification.get("matchedRate") or 0
        # NOT_COVERED / UNMAPPED_AMBIGUOUS / DUPLICATE_QUANTITY: withheld pending manual review.

    duplicate_leakage = sum(finding.get("variance") or 0 for finding in duplicate_findings)
    gross_recommended = max(gross_recommended - duplicate_leakage, 0)

    sum_insured_cap_applied = False
    sum_insured = policy_summary.get("sumInsuredAmount")
    if policy_summary.get("policyAvailable") and sum_insured is not None and gross_recommended > sum_insured:
        gross_recommended = sum_insured
        sum_insured_cap_applied = True

    copay_pct = policy_summary.get("copayPercentage") or 0
    copay_amount = round(gross_recommended * copay_pct / 100, 2)
    insurer_payable = round(gross_recommended - copay_amount, 2)

    return {
        "claimedAmount": claimed_amount,
        "recommendedSettlementAmount": round(gross_recommended, 2),
        "withheldAmount": round(claimed_amount - gross_recommended, 2),
        "sumInsuredCapApplied": sum_insured_cap_applied,
        "copayAmount": copay_amount,
        "insurerPayableAmount": insurer_payable,
    }
