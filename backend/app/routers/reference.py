from fastapi import APIRouter

from app import graph_repo
from app.constants import ITEM_TYPES

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/hospitals")
def get_hospitals():
    return graph_repo.list_hospitals()


@router.get("/procedures")
def get_procedures():
    return graph_repo.list_procedures()


@router.get("/item-types")
def get_item_types():
    return ITEM_TYPES


@router.get("/tariff-item-types")
def get_tariff_item_types(hospital_id: str, procedure: str):
    return graph_repo.list_item_types_for_procedure(hospital_id, procedure)
