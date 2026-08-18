import json

from app.db import get_session
from app.schemas import ClaimIn


def create_claim_graph(
    claim_id: str,
    claim: ClaimIn,
    source_type: str = "MANUAL",
    source_file_names: list[str] | None = None,
) -> list[dict]:
    claimed_amount = sum(item.amount * item.quantity for item in claim.billItems)

    with get_session() as session:
        session.run(
            """
            MERGE (p:Patient {patientId: $patientId})
              ON CREATE SET p.name = $patientName
            MERGE (pol:Policy {policyNumber: $policyNumber})
            MERGE (p)-[:HAS_POLICY]->(pol)
            MERGE (h:Hospital {hospitalId: $hospitalId})
            MERGE (doc:Doctor {name: $doctorName})
            MERGE (doc)-[:WORKS_AT]->(h)
            MERGE (diag:Diagnosis {name: $diagnosis})
            MERGE (proc:Procedure {name: $procedure})
            MERGE (c:Claim {claimId: $claimId})
            SET c.admissionDate = $admissionDate,
                c.dischargeDate = $dischargeDate,
                c.lengthOfStayDays = $lengthOfStayDays,
                c.claimedAmount = $claimedAmount,
                c.status = 'PROCESSING',
                c.sourceType = $sourceType,
                c.sourceFileNames = $sourceFileNames,
                c.createdAt = coalesce(c.createdAt, datetime())
            MERGE (p)-[:HAS_CLAIM]->(c)
            MERGE (c)-[:SUBMITTED_BY]->(h)
            MERGE (c)-[:TREATED_BY]->(doc)
            MERGE (c)-[:HAS_DIAGNOSIS]->(diag)
            MERGE (c)-[:HAS_PROCEDURE]->(proc)
            """,
            patientId=claim.patientId,
            patientName=claim.patientName,
            policyNumber=claim.policyNumber,
            hospitalId=claim.hospitalId,
            doctorName=claim.doctorName,
            diagnosis=claim.diagnosis,
            procedure=claim.procedure,
            claimId=claim_id,
            admissionDate=claim.admissionDate,
            dischargeDate=claim.dischargeDate,
            lengthOfStayDays=claim.lengthOfStayDays,
            claimedAmount=claimed_amount,
            sourceType=source_type,
            sourceFileNames=source_file_names or [],
        )

        created_items = []
        for idx, item in enumerate(claim.billItems):
            bill_item_id = f"{claim_id}-BI{idx + 1}"
            session.run(
                """
                MATCH (c:Claim {claimId: $claimId})
                CREATE (b:BillItem {
                    billItemId: $billItemId,
                    description: $description,
                    itemType: $itemType,
                    amount: $amount,
                    quantity: $quantity
                })
                CREATE (c)-[:HAS_BILL_ITEM]->(b)
                """,
                claimId=claim_id,
                billItemId=bill_item_id,
                description=item.description,
                itemType=item.itemType,
                amount=item.amount,
                quantity=item.quantity,
            )
            created_items.append(
                {
                    "billItemId": bill_item_id,
                    "description": item.description,
                    "itemType": item.itemType,
                    "amount": item.amount,
                    "quantity": item.quantity,
                }
            )

        return created_items


def create_tariff_items(hospital_id: str, items: list[dict]) -> None:
    """items: list of {tariffItemId, description, category, procedure, rate}."""
    with get_session() as session:
        for item in items:
            session.run(
                """
                MATCH (h:Hospital {hospitalId: $hospitalId})
                MERGE (t:TariffItem {tariffItemId: $tariffItemId})
                SET t.description = $description,
                    t.category = $category,
                    t.procedure = $procedure,
                    t.rate = $rate
                MERGE (h)-[:HAS_TARIFF_ITEM]->(t)
                """,
                hospitalId=hospital_id,
                tariffItemId=item["tariffItemId"],
                description=item["description"],
                category=item["category"],
                procedure=item["procedure"],
                rate=item["rate"],
            )


def list_tariff_catalog(hospital_id: str) -> list[dict]:
    with get_session() as session:
        result = session.run(
            """
            MATCH (h:Hospital {hospitalId: $hospitalId})-[:HAS_TARIFF_ITEM]->(t:TariffItem)
            RETURN t.tariffItemId AS tariffItemId, t.description AS description,
                   t.category AS category, t.procedure AS procedure, t.rate AS rate
            """,
            hospitalId=hospital_id,
        )
        return [dict(record) for record in result]


def has_tariff_catalog(hospital_id: str) -> bool:
    with get_session() as session:
        result = session.run(
            """
            MATCH (h:Hospital {hospitalId: $hospitalId})-[:HAS_TARIFF_ITEM]->(t:TariffItem)
            RETURN count(t) > 0 AS hasCatalog
            """,
            hospitalId=hospital_id,
        )
        record = result.single()
        return bool(record["hasCatalog"]) if record else False


def save_bill_item_classification(bill_item_id: str, classification: dict) -> None:
    """classification keys: status, confidence, matchedTariffItemId, matchedTariffDescription, matchedRate, variance."""
    with get_session() as session:
        session.run(
            """
            MATCH (b:BillItem {billItemId: $billItemId})
            SET b.matchStatus = $status,
                b.matchConfidence = $confidence,
                b.matchedTariffDescription = $matchedTariffDescription,
                b.matchedRate = $matchedRate,
                b.matchVariance = $variance
            """,
            billItemId=bill_item_id,
            status=classification["status"],
            confidence=classification["confidence"],
            matchedTariffDescription=classification.get("matchedTariffDescription"),
            matchedRate=classification.get("matchedRate"),
            variance=classification.get("variance"),
        )
        tariff_item_id = classification.get("matchedTariffItemId")
        if tariff_item_id:
            session.run(
                """
                MATCH (b:BillItem {billItemId: $billItemId})
                MATCH (t:TariffItem {tariffItemId: $tariffItemId})
                MERGE (b)-[:MATCHED_TO]->(t)
                """,
                billItemId=bill_item_id,
                tariffItemId=tariff_item_id,
            )


def seed_policy(policy_number: str, plan_name: str, sum_insured: float, room_rent_limit: float, copay_pct: float) -> None:
    with get_session() as session:
        session.run(
            """
            MERGE (pol:Policy {policyNumber: $policyNumber})
            SET pol.planName = $planName,
                pol.sumInsuredAmount = $sumInsured,
                pol.roomRentLimitPerDay = $roomRentLimit,
                pol.copayPercentage = $copayPct
            """,
            policyNumber=policy_number,
            planName=plan_name,
            sumInsured=sum_insured,
            roomRentLimit=room_rent_limit,
            copayPct=copay_pct,
        )


def get_policy(policy_number: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            """
            MATCH (pol:Policy {policyNumber: $policyNumber})
            WHERE pol.sumInsuredAmount IS NOT NULL
            RETURN pol.policyNumber AS policyNumber, pol.planName AS planName,
                   pol.sumInsuredAmount AS sumInsuredAmount,
                   pol.roomRentLimitPerDay AS roomRentLimitPerDay,
                   pol.copayPercentage AS copayPercentage
            """,
            policyNumber=policy_number,
        )
        record = result.single()
        return dict(record) if record else None


def save_finding(
    claim_id: str,
    bill_item_ids: list[str] | None,
    tariff_item_id: str | None,
    finding: dict,
) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (c:Claim {claimId: $claimId})
            CREATE (f:Finding {
                findingId: $findingId,
                agent: $agent,
                type: $type,
                description: $description,
                reason: $reason,
                billedAmount: $billedAmount,
                allowedAmount: $allowedAmount,
                variance: $variance,
                confidence: $confidence,
                recommendedAction: $recommendedAction,
                source: $source
            })
            CREATE (c)-[:HAS_FINDING]->(f)
            """,
            claimId=claim_id,
            **finding,
        )
        for bill_item_id in bill_item_ids or []:
            session.run(
                """
                MATCH (f:Finding {findingId: $findingId})
                MATCH (b:BillItem {billItemId: $billItemId})
                MERGE (f)-[:EVIDENCED_BY]->(b)
                """,
                findingId=finding["findingId"],
                billItemId=bill_item_id,
            )
        if tariff_item_id:
            session.run(
                """
                MATCH (f:Finding {findingId: $findingId})
                MATCH (t:TariffItem {tariffItemId: $tariffItemId})
                MERGE (f)-[:BASED_ON]->(t)
                """,
                findingId=finding["findingId"],
                tariffItemId=tariff_item_id,
            )


def update_claim_result(
    claim_id: str,
    risk_level: str,
    potential_leakage: float,
    summary_json: str,
    pipeline_json: str,
    status: str,
    policy_json: str | None,
    settlement_json: str | None,
    recommended_settlement_amount: float | None,
) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (c:Claim {claimId: $claimId})
            SET c.riskLevel = $riskLevel,
                c.potentialLeakage = $potentialLeakage,
                c.summary = $summaryJson,
                c.pipeline = $pipelineJson,
                c.policy = $policyJson,
                c.settlement = $settlementJson,
                c.recommendedSettlementAmount = $recommendedSettlementAmount,
                c.status = $status
            """,
            claimId=claim_id,
            riskLevel=risk_level,
            potentialLeakage=potential_leakage,
            summaryJson=summary_json,
            pipelineJson=pipeline_json,
            policyJson=policy_json,
            settlementJson=settlement_json,
            recommendedSettlementAmount=recommended_settlement_amount,
            status=status,
        )


def find_hospital_by_name(name: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            """
            MATCH (h:Hospital)
            WHERE toLower(h.name) CONTAINS toLower($name) OR toLower($name) CONTAINS toLower(h.name)
            RETURN h.hospitalId AS hospitalId, h.name AS name
            ORDER BY size(h.name) DESC
            LIMIT 1
            """,
            name=name,
        )
        record = result.single()
        return dict(record) if record else None


def create_hospital(hospital_id: str, name: str) -> None:
    with get_session() as session:
        session.run(
            "MERGE (h:Hospital {hospitalId: $hospitalId}) ON CREATE SET h.name = $name",
            hospitalId=hospital_id,
            name=name,
        )


def update_claim_decision(claim_id: str, decision: str, note: str | None) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (c:Claim {claimId: $claimId})
            SET c.status = $decision,
                c.decisionNote = $note,
                c.decidedAt = datetime()
            """,
            claimId=claim_id,
            decision=decision,
            note=note,
        )


def list_claims() -> list[dict]:
    with get_session() as session:
        result = session.run(
            """
            MATCH (c:Claim)-[:SUBMITTED_BY]->(h:Hospital)
            OPTIONAL MATCH (p:Patient)-[:HAS_CLAIM]->(c)
            OPTIONAL MATCH (c)-[:HAS_PROCEDURE]->(proc:Procedure)
            RETURN c.claimId AS claimId,
                   p.name AS patientName,
                   h.name AS hospitalName,
                   proc.name AS procedure,
                   c.claimedAmount AS claimedAmount,
                   c.riskLevel AS riskLevel,
                   c.potentialLeakage AS potentialLeakage,
                   c.recommendedSettlementAmount AS recommendedSettlementAmount,
                   c.status AS status,
                   toString(c.createdAt) AS createdAt
            ORDER BY c.createdAt DESC
            """
        )
        return [dict(record) for record in result]


def get_claim_detail(claim_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            """
            MATCH (c:Claim {claimId: $claimId})-[:SUBMITTED_BY]->(h:Hospital)
            OPTIONAL MATCH (p:Patient)-[:HAS_CLAIM]->(c)
            OPTIONAL MATCH (c)-[:TREATED_BY]->(doc:Doctor)
            OPTIONAL MATCH (c)-[:HAS_DIAGNOSIS]->(diag:Diagnosis)
            OPTIONAL MATCH (c)-[:HAS_PROCEDURE]->(proc:Procedure)
            OPTIONAL MATCH (c)-[:HAS_BILL_ITEM]->(b:BillItem)
            OPTIONAL MATCH (c)-[:HAS_FINDING]->(f:Finding)
            RETURN c AS claim, h AS hospital, p AS patient, doc AS doctor,
                   diag AS diagnosis, proc AS procedure,
                   collect(DISTINCT b) AS billItems,
                   collect(DISTINCT f) AS findings
            """,
            claimId=claim_id,
        )
        record = result.single()
        if not record:
            return None

        def node_to_dict(node):
            return dict(node) if node is not None else None

        claim_dict = node_to_dict(record["claim"])
        if claim_dict and "createdAt" in claim_dict:
            claim_dict["createdAt"] = str(claim_dict["createdAt"])
        if claim_dict and "decidedAt" in claim_dict and claim_dict["decidedAt"] is not None:
            claim_dict["decidedAt"] = str(claim_dict["decidedAt"])
        if claim_dict and claim_dict.get("summary"):
            try:
                claim_dict["summary"] = json.loads(claim_dict["summary"])
            except (TypeError, json.JSONDecodeError):
                pass
        if claim_dict and claim_dict.get("pipeline"):
            try:
                claim_dict["pipeline"] = json.loads(claim_dict["pipeline"])
            except (TypeError, json.JSONDecodeError):
                pass
        for json_field in ("policy", "settlement"):
            if claim_dict and claim_dict.get(json_field):
                try:
                    claim_dict[json_field] = json.loads(claim_dict[json_field])
                except (TypeError, json.JSONDecodeError):
                    pass

        bill_items = [dict(b) for b in record["billItems"] if b is not None]
        classifications = [
            {
                "billItemId": b["billItemId"],
                "description": b["description"],
                "itemType": b["itemType"],
                "billedAmount": b["amount"] * b.get("quantity", 1),
                "status": b["matchStatus"],
                "confidence": b.get("matchConfidence"),
                "matchedTariffDescription": b.get("matchedTariffDescription"),
                "matchedRate": b.get("matchedRate"),
                "variance": b.get("matchVariance"),
            }
            for b in bill_items
            if b.get("matchStatus")
        ]

        return {
            "claim": claim_dict,
            "hospital": node_to_dict(record["hospital"]),
            "patient": node_to_dict(record["patient"]),
            "doctor": node_to_dict(record["doctor"]),
            "diagnosis": node_to_dict(record["diagnosis"]),
            "procedure": node_to_dict(record["procedure"]),
            "billItems": bill_items,
            "classifications": classifications,
            "findings": [dict(f) for f in record["findings"] if f is not None],
        }


def list_hospitals() -> list[dict]:
    with get_session() as session:
        result = session.run("MATCH (h:Hospital) RETURN h.hospitalId AS hospitalId, h.name AS name ORDER BY h.name")
        return [dict(record) for record in result]


def list_procedures() -> list[dict]:
    with get_session() as session:
        result = session.run("MATCH (proc:Procedure) RETURN proc.name AS name ORDER BY proc.name")
        return [dict(record) for record in result]


