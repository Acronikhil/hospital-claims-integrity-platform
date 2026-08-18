"""Policy Compliance Agent.

Compares the claim against the patient's policy terms - sum insured cap
and room rent sub-limit - using policy data stored in the knowledge
graph. Never invents policy terms: if no reference data exists for the
claim's policy number, it reports that plainly instead of guessing, the
same pattern used for hospitals with no tariff catalog.
"""
import uuid

from app import graph_repo

SOURCE = "Policy Master (Neo4j: Policy node - sumInsuredAmount / roomRentLimitPerDay / copayPercentage)"


def _finding(ftype: str, description: str, reason: str, billed, allowed, variance, confidence, action: str) -> dict:
    return {
        "findingId": f"FND-{uuid.uuid4().hex[:8]}",
        "agent": "Policy Compliance Agent",
        "type": ftype,
        "description": description,
        "reason": reason,
        "billedAmount": billed,
        "allowedAmount": allowed,
        "variance": variance,
        "confidence": confidence,
        "recommendedAction": action,
        "source": SOURCE,
    }


def run(
    claim_id: str,
    policy_number: str,
    claimed_amount: float,
    bill_items: list[dict],
    length_of_stay_days: int,
) -> tuple[list[dict], dict]:
    policy = graph_repo.get_policy(policy_number)

    if policy is None:
        return [], {
            "policyAvailable": False,
            "policyNumber": policy_number,
            "planName": None,
            "sumInsuredAmount": None,
            "roomRentLimitPerDay": None,
            "copayPercentage": None,
        }

    findings = []

    sum_insured = policy["sumInsuredAmount"]
    if claimed_amount > sum_insured:
        excess = round(claimed_amount - sum_insured, 2)
        finding = _finding(
            "sum_insured_exceeded",
            "Claimed amount exceeds policy sum insured",
            f"Claimed amount (₹{claimed_amount:,.0f}) exceeds the policy's sum insured "
            f"(₹{sum_insured:,.0f}) by ₹{excess:,.0f}.",
            claimed_amount, sum_insured, excess, 100,
            "Cap settlement at the sum insured; the balance is not payable under this policy.",
        )
        graph_repo.save_finding(claim_id=claim_id, bill_item_ids=None, tariff_item_id=None, finding=finding)
        findings.append(finding)

    room_items = [i for i in bill_items if i["itemType"] == "Room Charges"]
    room_rent_limit = policy.get("roomRentLimitPerDay")
    if room_items and room_rent_limit and length_of_stay_days > 0:
        total_room_amount = sum(i["amount"] * i.get("quantity", 1) for i in room_items)
        per_day = total_room_amount / length_of_stay_days
        if per_day > room_rent_limit * 1.005:
            total_excess = round((per_day - room_rent_limit) * length_of_stay_days, 2)
            finding = _finding(
                "room_rent_limit_exceeded",
                "Room rent exceeds the policy's daily sub-limit",
                f"Room charges average ₹{per_day:,.0f}/day across {length_of_stay_days} day(s), above "
                f"the policy's room rent sub-limit of ₹{room_rent_limit:,.0f}/day.",
                total_room_amount, room_rent_limit * length_of_stay_days, total_excess, 90,
                "Cap room charges at the policy's daily sub-limit. Many policies also apply a "
                "proportionate deduction to associated charges (OT/surgeon/nursing) when the room "
                "category exceeds the eligible limit - verify this manually; it is not computed here.",
            )
            graph_repo.save_finding(
                claim_id=claim_id,
                bill_item_ids=[i["billItemId"] for i in room_items],
                tariff_item_id=None,
                finding=finding,
            )
            findings.append(finding)

    policy_summary = {
        "policyAvailable": True,
        "policyNumber": policy["policyNumber"],
        "planName": policy.get("planName"),
        "sumInsuredAmount": sum_insured,
        "roomRentLimitPerDay": room_rent_limit,
        "copayPercentage": policy.get("copayPercentage") or 0,
    }
    return findings, policy_summary
