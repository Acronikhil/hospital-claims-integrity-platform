"""Duplicate Billing Agent.

Flags line items on the same claim that share a description and amount,
which typically indicates the same service or medicine billed more than
once.
"""
import uuid
from collections import defaultdict

from app import graph_repo


def run(claim_id: str, bill_items: list[dict]) -> list[dict]:
    findings = []
    groups: dict[tuple[str, float], list[dict]] = defaultdict(list)

    for item in bill_items:
        key = (item["description"].strip().lower(), item["amount"])
        groups[key].append(item)

    for (description, amount), items in groups.items():
        if len(items) < 2:
            continue

        duplicate_count = len(items) - 1
        potential_leakage = round(amount * duplicate_count, 2)
        finding_id = f"FND-{uuid.uuid4().hex[:8]}"

        finding = {
            "findingId": finding_id,
            "agent": "Duplicate Billing Agent",
            "type": "duplicate_billing",
            "description": f"Potential duplicate billing for '{items[0]['description']}'",
            "reason": (
                f"'{items[0]['description']}' (₹{amount:,.0f}) appears {len(items)} times on this claim "
                f"with an identical amount, suggesting the same service or item was billed more than once."
            ),
            "billedAmount": round(amount * len(items), 2),
            "allowedAmount": round(amount, 2),
            "variance": potential_leakage,
            "confidence": 85,
            "recommendedAction": "Verify with hospital whether the repeated charge reflects distinct services.",
            "source": "Claim bill items (Neo4j: Claim-HAS_BILL_ITEM->BillItem)",
        }

        graph_repo.save_finding(
            claim_id=claim_id,
            bill_item_ids=[item["billItemId"] for item in items],
            tariff_id=None,
            finding=finding,
        )

        findings.append(finding)

    return findings
