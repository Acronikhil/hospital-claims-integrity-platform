"""Risk Assessment Engine.

Aggregates findings from all agents into an overall risk level and total
potential leakage figure. This is a deterministic scoring rule, not a
black-box score - the thresholds are explicit and auditable.
"""

HIGH_LEAKAGE_THRESHOLD = 50_000
MEDIUM_LEAKAGE_THRESHOLD = 10_000
HIGH_FINDING_COUNT = 3


def assess(findings: list[dict]) -> tuple[str, float]:
    potential_leakage = round(sum(f.get("variance") or 0 for f in findings), 2)

    if not findings:
        return "LOW", 0.0

    if potential_leakage >= HIGH_LEAKAGE_THRESHOLD or len(findings) >= HIGH_FINDING_COUNT:
        risk_level = "HIGH"
    elif potential_leakage >= MEDIUM_LEAKAGE_THRESHOLD:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return risk_level, potential_leakage
