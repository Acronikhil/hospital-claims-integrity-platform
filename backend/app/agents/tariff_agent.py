"""Tariff Intelligence Agent.

Compares each billed line item against the hospital's contracted tariff for
the claimed procedure, retrieved from the Neo4j knowledge graph. Never
invents an allowed amount - it only reasons over tariff nodes that exist
in the graph.
"""
import uuid

from app import graph_repo


def run(claim_id: str, hospital_id: str, procedure: str, bill_items: list[dict]) -> tuple[list[dict], bool]:
    findings = []
    tariff_reference_available = graph_repo.has_tariff_reference(hospital_id, procedure)

    if not tariff_reference_available:
        return findings, False

    for item in bill_items:
        tariff = graph_repo.get_tariff(hospital_id, procedure, item["itemType"])
        if tariff is None:
            continue

        allowed_amount = tariff["allowedAmount"]
        billed_amount = item["amount"] * item.get("quantity", 1)

        if billed_amount <= allowed_amount:
            continue

        variance = round(billed_amount - allowed_amount, 2)
        finding_id = f"FND-{uuid.uuid4().hex[:8]}"

        finding = {
            "findingId": finding_id,
            "agent": "Tariff Intelligence Agent",
            "type": "tariff_variance",
            "description": f"Potential excess charge on {item['itemType']}",
            "reason": (
                f"Billed amount (₹{billed_amount:,.0f}) exceeds the contracted tariff "
                f"(₹{allowed_amount:,.0f}) for {item['itemType']} under {procedure}."
            ),
            "billedAmount": billed_amount,
            "allowedAmount": allowed_amount,
            "variance": variance,
            "confidence": 95,
            "recommendedAction": "Query hospital for supporting documentation or apply deduction.",
            "source": "Hospital Tariff Master (Neo4j: Hospital-HAS_TARIFF->Tariff-APPLIES_TO->Procedure)",
        }

        graph_repo.save_finding(
            claim_id=claim_id,
            bill_item_ids=[item["billItemId"]],
            tariff_id=tariff["tariffId"],
            finding=finding,
        )
        findings.append(finding)

    return findings, True
