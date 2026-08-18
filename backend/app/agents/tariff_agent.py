"""Tariff Matching Agent.

Maps every billed line item to its corresponding entry in the hospital's
tariff catalog using fuzzy text matching (rapidfuzz - local, no external
AI API), then classifies each item into one of the states from the
claims-integrity design doc: Matched & Within Rate, Matched & Over Rate,
Matched & Under Rate, Not Covered, or Unmapped/Ambiguous. Findings (used
for risk scoring) are only raised for the states that represent leakage
risk or need manual review - a clean match never generates a finding.
"""
import uuid

from rapidfuzz import fuzz, process

from app import graph_repo
from app.constants import (
    MATCHED_OVER_RATE,
    MATCHED_UNDER_RATE,
    MATCHED_WITHIN_RATE,
    NOT_COVERED,
    UNMAPPED_AMBIGUOUS,
)

CONFIDENT_MATCH_THRESHOLD = 70  # >= this: treat as a confident tariff match
NOT_COVERED_THRESHOLD = 40      # below this: nothing in the catalog resembles the item
RATE_TOLERANCE = 0.005          # 0.5% tolerance to absorb rounding noise


def _best_match(description: str, catalog: list[dict], procedure: str) -> tuple[dict | None, int]:
    if not catalog:
        return None, 0

    # Prefer candidates scoped to the claim's procedure - the same category
    # (e.g. "OT Charges") can carry very different contracted rates by procedure.
    scoped = [c for c in catalog if c["procedure"] == procedure]
    candidates = scoped or catalog

    # token_set_ratio (not token_sort_ratio) so a short bill description like "OT Charges"
    # scores highly against a longer catalog entry like "OT Charges - Cataract Surgery" -
    # it credits the shared token subset instead of penalizing the catalog entry's extra words.
    choices = {c["tariffItemId"]: c["description"] for c in candidates}
    result = process.extractOne(description, choices, scorer=fuzz.token_set_ratio)
    if result is None:
        return None, 0

    _matched_description, score, tariff_item_id = result
    matched = next(c for c in candidates if c["tariffItemId"] == tariff_item_id)
    return matched, int(score)


def _finding(agent: str, ftype: str, description: str, reason: str, billed: float, allowed, variance, confidence, action, source) -> dict:
    return {
        "findingId": f"FND-{uuid.uuid4().hex[:8]}",
        "agent": agent,
        "type": ftype,
        "description": description,
        "reason": reason,
        "billedAmount": billed,
        "allowedAmount": allowed,
        "variance": variance,
        "confidence": confidence,
        "recommendedAction": action,
        "source": source,
    }


def run(claim_id: str, hospital_id: str, procedure: str, bill_items: list[dict]) -> tuple[list[dict], list[dict], bool]:
    findings: list[dict] = []
    classifications: list[dict] = []

    catalog = graph_repo.list_tariff_catalog(hospital_id)
    tariff_reference_available = len(catalog) > 0

    for item in bill_items:
        billed_amount = round(item["amount"] * item.get("quantity", 1), 2)
        base = {
            "billItemId": item["billItemId"],
            "description": item["description"],
            "itemType": item["itemType"],
            "billedAmount": billed_amount,
        }

        if not tariff_reference_available:
            classification = {
                **base,
                "status": UNMAPPED_AMBIGUOUS,
                "confidence": 0,
                "matchedTariffDescription": None,
                "matchedRate": None,
                "variance": None,
                "matchedTariffItemId": None,
            }
            classifications.append(classification)
            graph_repo.save_bill_item_classification(item["billItemId"], classification)
            continue

        matched, score = _best_match(item["description"], catalog, procedure)
        source = "Hospital Tariff Catalog (Neo4j: Hospital-HAS_TARIFF_ITEM->TariffItem, fuzzy-matched via rapidfuzz)"
        finding = None

        if matched is None or score < NOT_COVERED_THRESHOLD:
            classification = {
                **base, "status": NOT_COVERED, "confidence": score,
                "matchedTariffDescription": None, "matchedRate": None,
                "variance": billed_amount, "matchedTariffItemId": None,
            }
            finding = _finding(
                "Tariff Matching Agent", "not_covered",
                f"'{item['description']}' not found in hospital tariff catalog",
                f"No entry in {hospital_id}'s tariff catalog resembles '{item['description']}' "
                f"(closest match confidence: {score}%). This item may not be covered under the "
                f"contracted tariff.",
                billed_amount, None, billed_amount, max(100 - score, 60),
                "Verify the item is contractually payable before approving; request hospital justification.",
                source,
            )
        elif score < CONFIDENT_MATCH_THRESHOLD:
            classification = {
                **base, "status": UNMAPPED_AMBIGUOUS, "confidence": score,
                "matchedTariffDescription": matched["description"], "matchedRate": matched["rate"],
                "variance": None, "matchedTariffItemId": matched["tariffItemId"],
            }
            finding = _finding(
                "Tariff Matching Agent", "unmapped_ambiguous",
                f"'{item['description']}' could not be confidently matched to a tariff entry",
                f"Closest tariff catalog match is '{matched['description']}' at only {score}% confidence "
                f"(below the {CONFIDENT_MATCH_THRESHOLD}% threshold for an automatic match). Needs manual "
                f"review to confirm the correct tariff line item.",
                billed_amount, matched["rate"], None, score,
                "Manually verify against the tariff master and confirm the correct classification.",
                source,
            )
        else:
            rate = matched["rate"]
            if billed_amount > rate * (1 + RATE_TOLERANCE):
                status = MATCHED_OVER_RATE
                variance = round(billed_amount - rate, 2)
                finding = _finding(
                    "Tariff Matching Agent", "tariff_variance",
                    f"Potential excess charge on {item['itemType']}",
                    f"Billed amount (₹{billed_amount:,.0f}) exceeds the contracted tariff rate "
                    f"(₹{rate:,.0f}) for '{matched['description']}' (matched at {score}% confidence).",
                    billed_amount, rate, variance, 95,
                    "Query hospital for supporting documentation or apply deduction.",
                    source,
                )
            elif billed_amount < rate * (1 - RATE_TOLERANCE):
                status = MATCHED_UNDER_RATE
                variance = None
            else:
                status = MATCHED_WITHIN_RATE
                variance = None

            classification = {
                **base, "status": status, "confidence": score,
                "matchedTariffDescription": matched["description"], "matchedRate": rate,
                "variance": variance, "matchedTariffItemId": matched["tariffItemId"],
            }

        classifications.append(classification)
        graph_repo.save_bill_item_classification(item["billItemId"], classification)

        if finding is not None:
            findings.append(finding)
            graph_repo.save_finding(
                claim_id=claim_id,
                bill_item_ids=[item["billItemId"]],
                tariff_item_id=classification["matchedTariffItemId"],
                finding=finding,
            )

    return findings, classifications, tariff_reference_available
