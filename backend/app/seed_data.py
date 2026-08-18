from app.db import get_session

HOSPITALS = [
    {"hospitalId": "H001", "name": "ABC Hospital", "city": "Mumbai"},
    {"hospitalId": "H002", "name": "XYZ Multispecialty Hospital", "city": "Pune"},
]

PROCEDURES = ["Cataract Surgery", "Cardiac Bypass Surgery"]

# (hospitalId, procedure, itemType, allowedAmount)
TARIFFS = [
    # ABC Hospital - Cataract Surgery
    ("H001", "Cataract Surgery", "OT Charges", 25000),
    ("H001", "Cataract Surgery", "Room Charges", 8000),
    ("H001", "Cataract Surgery", "Surgeon Fee", 20000),
    ("H001", "Cataract Surgery", "Consumables", 8000),
    ("H001", "Cataract Surgery", "Nursing Charges", 3000),
    ("H001", "Cataract Surgery", "Medicines", 4000),
    ("H001", "Cataract Surgery", "Investigation", 3000),
    # XYZ Hospital - Cataract Surgery
    ("H002", "Cataract Surgery", "OT Charges", 27000),
    ("H002", "Cataract Surgery", "Room Charges", 9000),
    ("H002", "Cataract Surgery", "Surgeon Fee", 22000),
    ("H002", "Cataract Surgery", "Consumables", 9000),
    ("H002", "Cataract Surgery", "Nursing Charges", 3500),
    ("H002", "Cataract Surgery", "Medicines", 4500),
    ("H002", "Cataract Surgery", "Investigation", 3500),
    # ABC Hospital - Cardiac Bypass Surgery
    ("H001", "Cardiac Bypass Surgery", "OT Charges", 150000),
    ("H001", "Cardiac Bypass Surgery", "Room Charges", 40000),
    ("H001", "Cardiac Bypass Surgery", "Surgeon Fee", 200000),
    ("H001", "Cardiac Bypass Surgery", "Consumables", 80000),
    ("H001", "Cardiac Bypass Surgery", "ICU Charges", 60000),
    ("H001", "Cardiac Bypass Surgery", "Investigation", 15000),
    # XYZ Hospital - Cardiac Bypass Surgery
    ("H002", "Cardiac Bypass Surgery", "OT Charges", 160000),
    ("H002", "Cardiac Bypass Surgery", "Room Charges", 45000),
    ("H002", "Cardiac Bypass Surgery", "Surgeon Fee", 210000),
    ("H002", "Cardiac Bypass Surgery", "Consumables", 85000),
    ("H002", "Cardiac Bypass Surgery", "ICU Charges", 65000),
    ("H002", "Cardiac Bypass Surgery", "Investigation", 18000),
]


def seed() -> None:
    with get_session() as session:
        for hospital in HOSPITALS:
            session.run(
                "MERGE (h:Hospital {hospitalId: $hospitalId}) SET h.name = $name, h.city = $city",
                **hospital,
            )

        for procedure in PROCEDURES:
            session.run("MERGE (proc:Procedure {name: $name})", name=procedure)

        for hospital_id, procedure, item_type, allowed_amount in TARIFFS:
            tariff_id = f"{hospital_id}-{procedure}-{item_type}".replace(" ", "_")
            session.run(
                """
                MATCH (h:Hospital {hospitalId: $hospitalId})
                MATCH (proc:Procedure {name: $procedure})
                MERGE (t:Tariff {tariffId: $tariffId})
                SET t.itemType = $itemType, t.allowedAmount = $allowedAmount
                MERGE (h)-[:HAS_TARIFF]->(t)
                MERGE (t)-[:APPLIES_TO]->(proc)
                """,
                hospitalId=hospital_id,
                procedure=procedure,
                tariffId=tariff_id,
                itemType=item_type,
                allowedAmount=allowed_amount,
            )
