"""Document Intelligence Agent.

Extracts structured claim data from one or more uploaded claim documents
(final bill, pre-authorization form, discharge summary, ...) using
pdfplumber for text/table extraction, with a Tesseract OCR fallback for
scanned/photographed pages that carry no text layer. Fully local - no
external AI API or key required, so extraction quality depends on the
document following a fairly consistent "label: value" + line-item table
layout (see README for the assumptions this makes).
"""
import io
import re
from datetime import date, datetime

import pdfplumber

from app.schemas import ExtractedBillItem, ExtractedClaim

try:
    import pytesseract
except ImportError:  # pragma: no cover - pytesseract is a required dependency, but degrade gracefully
    pytesseract = None

METHOD = "pdfplumber + Tesseract OCR (local, no external AI API)"

FIELD_PATTERNS: dict[str, list[str]] = {
    "patientName": [
        r"patient\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
        r"name\s*of\s*patient\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
    ],
    "patientId": [
        r"(?:patient\s*id|uhid|mrn|ip\s*no\.?)\s*[:\-]\s*([A-Za-z0-9\-\/]{3,20})",
    ],
    "policyNumber": [
        r"policy\s*(?:no\.?|number)\s*[:\-]\s*([A-Za-z0-9\-\/]{4,30})",
    ],
    "hospitalName": [
        r"hospital\s*name\s*[:\-]\s*([A-Za-z][A-Za-z0-9 .&,\-]{2,80})",
    ],
    "doctorName": [
        r"(?:consultant|treating\s*doctor|attending\s*doctor)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,50})",
        r"doctor\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,50})",
    ],
    "diagnosis": [
        r"diagnosis\s*[:\-]\s*(.+)",
    ],
    "procedure": [
        r"(?:procedure|surgery\s*(?:performed|done)?)\s*[:\-]\s*(.+)",
    ],
    "admissionDate": [
        r"(?:admission\s*date|date\s*of\s*admission|admitted\s*on)\s*[:\-]\s*"
        r"([\d]{1,2}[\/\-\.][\d]{1,2}[\/\-\.][\d]{2,4}|[\d]{4}-[\d]{2}-[\d]{2})",
    ],
    "dischargeDate": [
        r"(?:discharge\s*date|date\s*of\s*discharge|discharged\s*on)\s*[:\-]\s*"
        r"([\d]{1,2}[\/\-\.][\d]{1,2}[\/\-\.][\d]{2,4}|[\d]{4}-[\d]{2}-[\d]{2})",
    ],
}

ITEM_TYPE_KEYWORDS = [
    ("OT Charges", ["ot charge", "operation theatre", "operation theater", "surgery charge"]),
    ("Room Charges", ["room rent", "room charge", "bed charge", "ward charge"]),
    ("Surgeon Fee", ["surgeon fee", "surgeon charge", "operating surgeon"]),
    ("Consumables", ["consumable"]),
    ("Nursing Charges", ["nursing"]),
    ("Medicines", ["medicine", "pharmacy", "drug"]),
    ("Investigation", ["investigation", "lab", "pathology", "x-ray", "xray", "mri", "ct scan", "ultrasound", "radiology"]),
    ("ICU Charges", ["icu"]),
    ("Doctor Consultation", ["consultation", "visit charge", "doctor fee", "physician fee"]),
]

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"]

EXCLUDED_LINE_KEYWORDS = (
    "total", "balance", "grand total", "subtotal", "net amount", "advance", "discount", "gst", "tax",
)

AMOUNT_LINE_RE = re.compile(
    r"^(?P<desc>[A-Za-z][A-Za-z0-9 .,()/\-]{2,60}?)\s+(?:Rs\.?|INR|₹)?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s*$"
)


def _normalize_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _guess_item_type(description: str) -> str:
    lowered = description.lower()
    for item_type, keywords in ITEM_TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return item_type
    return "Other"


def _page_text(page) -> str:
    text = page.extract_text() or ""
    if len(text.strip()) >= 20 or pytesseract is None:
        return text
    # No usable text layer - likely a scanned/photographed page. OCR it.
    try:
        image = page.to_image(resolution=200).original
        return pytesseract.image_to_string(image)
    except Exception:
        return text


def _extract_bill_items_from_table(table: list[list[str | None]]) -> list[ExtractedBillItem]:
    if not table or len(table) < 2:
        return []

    header = [str(cell or "").strip().lower() for cell in table[0]]
    desc_idx = next(
        (i for i, h in enumerate(header) if any(k in h for k in ("description", "particular", "item", "service"))),
        None,
    )
    amount_idx = next(
        (i for i, h in enumerate(header) if any(k in h for k in ("amount", "charge", "rate", "total"))),
        None,
    )
    if desc_idx is None or amount_idx is None:
        return []

    items = []
    for row in table[1:]:
        if desc_idx >= len(row) or amount_idx >= len(row):
            continue
        desc = (row[desc_idx] or "").strip()
        amount_raw = (row[amount_idx] or "").strip()
        if not desc or not amount_raw or any(k in desc.lower() for k in EXCLUDED_LINE_KEYWORDS):
            continue
        amount_clean = re.sub(r"[^\d.]", "", amount_raw)
        if not amount_clean:
            continue
        try:
            amount = float(amount_clean)
        except ValueError:
            continue
        if amount <= 0:
            continue
        items.append(ExtractedBillItem(description=desc, itemType=_guess_item_type(desc), amount=amount, quantity=1))
    return items


def _extract_bill_items_from_text(text: str) -> list[ExtractedBillItem]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 90 or any(k in line.lower() for k in EXCLUDED_LINE_KEYWORDS):
            continue
        match = AMOUNT_LINE_RE.match(line)
        if not match:
            continue
        desc = match.group("desc").strip(" -:")
        amount_clean = match.group("amount").replace(",", "")
        try:
            amount = float(amount_clean)
        except ValueError:
            continue
        if amount <= 0:
            continue
        items.append(ExtractedBillItem(description=desc, itemType=_guess_item_type(desc), amount=amount, quantity=1))
    return items


def extract_claim_from_documents(files: list[tuple[str, bytes]]) -> ExtractedClaim:
    """files: list of (filename, pdf_bytes) tuples, all belonging to the same claim.

    Fields are merged across documents - the first document (in upload order) that
    contains a labeled match for a field wins. Bill items are only taken from tables
    or amount-shaped lines, never invented.
    """
    fields: dict[str, str] = {}
    bill_items: list[ExtractedBillItem] = []
    fallback_title: str | None = None

    for _filename, pdf_bytes in files:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                text = _page_text(page)

                if fallback_title is None:
                    for line in text.splitlines():
                        stripped = line.strip()
                        if len(stripped) >= 4:
                            fallback_title = stripped
                            break

                for field, patterns in FIELD_PATTERNS.items():
                    if field in fields:
                        continue
                    match = _first_match(patterns, text)
                    if match:
                        fields[field] = match

                for table in page.extract_tables() or []:
                    bill_items.extend(_extract_bill_items_from_table(table))

                if not bill_items and page_idx == 0:
                    bill_items.extend(_extract_bill_items_from_text(text))

    if not bill_items:
        for _filename, pdf_bytes in files:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    bill_items.extend(_extract_bill_items_from_text(_page_text(page)))
            if bill_items:
                break

    admission = _normalize_date(fields["admissionDate"]) if fields.get("admissionDate") else None
    discharge = _normalize_date(fields["dischargeDate"]) if fields.get("dischargeDate") else None
    length_of_stay = None
    if admission and discharge:
        length_of_stay = max((date.fromisoformat(discharge) - date.fromisoformat(admission)).days, 0)

    return ExtractedClaim(
        patientId=fields.get("patientId"),
        patientName=fields.get("patientName") or "Unknown Patient",
        policyNumber=fields.get("policyNumber") or "UNKNOWN",
        hospitalName=fields.get("hospitalName") or fallback_title or "Unknown Hospital",
        doctorName=fields.get("doctorName") or "Unknown Doctor",
        diagnosis=fields.get("diagnosis") or "Not specified",
        procedure=fields.get("procedure") or "Not specified",
        admissionDate=admission or discharge or date.today().isoformat(),
        dischargeDate=discharge or admission or date.today().isoformat(),
        lengthOfStayDays=length_of_stay if length_of_stay is not None else 1,
        billItems=bill_items,
    )
