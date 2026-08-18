from contextlib import contextmanager
from neo4j import GraphDatabase

from app.config import settings

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


@contextmanager
def get_session():
    driver = get_driver()
    session = driver.session()
    try:
        yield session
    finally:
        session.close()


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


CONSTRAINTS = [
    "CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patientId IS UNIQUE",
    "CREATE CONSTRAINT policy_number IF NOT EXISTS FOR (pol:Policy) REQUIRE pol.policyNumber IS UNIQUE",
    "CREATE CONSTRAINT hospital_id IF NOT EXISTS FOR (h:Hospital) REQUIRE h.hospitalId IS UNIQUE",
    "CREATE CONSTRAINT procedure_name IF NOT EXISTS FOR (proc:Procedure) REQUIRE proc.name IS UNIQUE",
    "CREATE CONSTRAINT diagnosis_name IF NOT EXISTS FOR (d:Diagnosis) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claimId IS UNIQUE",
    "CREATE CONSTRAINT bill_item_id IF NOT EXISTS FOR (b:BillItem) REQUIRE b.billItemId IS UNIQUE",
    "CREATE CONSTRAINT tariff_item_id IF NOT EXISTS FOR (t:TariffItem) REQUIRE t.tariffItemId IS UNIQUE",
    "CREATE CONSTRAINT finding_id IF NOT EXISTS FOR (f:Finding) REQUIRE f.findingId IS UNIQUE",
]


def init_constraints():
    with get_session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
