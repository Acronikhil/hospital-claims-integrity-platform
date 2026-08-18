from app.db import get_session
from app import graph_repo

HOSPITALS = [
    {"hospitalId": "H001", "name": "ABC Hospital", "city": "Mumbai"},
    {"hospitalId": "H002", "name": "XYZ Multispecialty Hospital", "city": "Pune"},
]

PROCEDURES = ["Cataract Surgery", "Cardiac Bypass Surgery"]

# (hospitalId, procedure, category/itemType, rate) - flattened into descriptive
# tariff catalog line items below, the way a real hospital tariff master reads.
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

# (policyNumber, planName, sumInsuredAmount, roomRentLimitPerDay, copayPercentage)
POLICIES = [
    ("POL-STANDARD-001", "Health Standard Plan", 500000, 5000, 10),
    ("POL-PREMIUM-001", "Health Premium Plan", 2000000, 15000, 0),
]


def _tariff_catalog_items() -> list[tuple[str, list[dict]]]:
    """Group the flat TARIFFS list into per-hospital tariff catalog line items."""
    by_hospital: dict[str, list[dict]] = {}
    for hospital_id, procedure, category, rate in TARIFFS:
        description = f"{category} - {procedure}"
        tariff_item_id = f"{hospital_id}-{procedure}-{category}".replace(" ", "_")
        by_hospital.setdefault(hospital_id, []).append(
            {
                "tariffItemId": tariff_item_id,
                "description": description,
                "category": category,
                "procedure": procedure,
                "rate": rate,
            }
        )
    return list(by_hospital.items())


def seed() -> None:
    with get_session() as session:
        for hospital in HOSPITALS:
            session.run(
                "MERGE (h:Hospital {hospitalId: $hospitalId}) SET h.name = $name, h.city = $city",
                **hospital,
            )

        for procedure in PROCEDURES:
            session.run("MERGE (proc:Procedure {name: $name})", name=procedure)

    for hospital_id, items in _tariff_catalog_items():
        graph_repo.create_tariff_items(hospital_id, items)

    for policy_number, plan_name, sum_insured, room_rent_limit, copay_pct in POLICIES:
        graph_repo.seed_policy(policy_number, plan_name, sum_insured, room_rent_limit, copay_pct)
