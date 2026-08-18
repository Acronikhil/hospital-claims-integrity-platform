ITEM_TYPES = [
    "OT Charges",
    "Room Charges",
    "Surgeon Fee",
    "Consumables",
    "Nursing Charges",
    "Medicines",
    "Investigation",
    "ICU Charges",
    "Doctor Consultation",
    "Other",
]

# Bill-item-to-tariff match classification, per the graph-matching design doc.
MATCHED_WITHIN_RATE = "MATCHED_WITHIN_RATE"
MATCHED_OVER_RATE = "MATCHED_OVER_RATE"
MATCHED_UNDER_RATE = "MATCHED_UNDER_RATE"
NOT_COVERED = "NOT_COVERED"
UNMAPPED_AMBIGUOUS = "UNMAPPED_AMBIGUOUS"
DUPLICATE_QUANTITY = "DUPLICATE_QUANTITY"
