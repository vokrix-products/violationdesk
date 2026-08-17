import csv
import datetime as dt
import io
import json
import os
import re


STATUSES = [
    "New",
    "Missing",
    "Valid",
    "Notice Sent",
    "In Cure",
    "Expired",
    "Fine Issued",
    "Flagged",
    "Closed",
    "Void",
]


FIELD_ALIASES = {
    "Received timestamp": ["received_timestamp", "received timestamp", "received", "timestamp"],
    "Received via": ["received_via", "received via", "channel"],
    "Complainant name": ["complainant_name", "complainant name", "complainant"],
    "Complainant email": ["complainant_email", "complainant email", "email"],
    "Complainant phone": ["complainant_phone", "complainant phone", "phone"],
    "Association/community name": ["association_name", "association", "community", "association name", "community name"],
    "Property address": ["property_address", "property address", "address", "property"],
    "Unit number": ["unit_number", "unit number", "unit"],
    "Violation category": ["violation_category", "violation category", "category"],
    "Violation description": ["violation_description", "violation description", "description", "violation"],
    "Photo evidence file reference(s)": ["photo_evidence", "photo evidence", "photo_evidence_file_reference", "photo_evidence_file_references", "photos", "evidence"],
    "Incident date": ["incident_date", "incident date", "date_of_incident"],
    "Reporter type": ["reporter_type", "reporter type", "reporter"],
    "Status": ["status", "violation_status", "record_status"],
    "Due date": ["due_date", "due date", "cure deadline", "deadline"],
}


def _normalize_key(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


ALIAS_TO_FIELD = {}
for _canonical, _aliases in FIELD_ALIASES.items():
    ALIAS_TO_FIELD[_normalize_key(_canonical)] = _canonical
    for _alias in _aliases:
        ALIAS_TO_FIELD[_normalize_key(_alias)] = _canonical


def _parse_date(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None

    try:
        if "T" in value:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.datetime.fromisoformat(value)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%m/%d/%y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return dt.datetime.strptime(value, fmt)
        except Exception:
            continue

    return None


def _due_date_value(value):
    parsed = _parse_date(value)
    if parsed is None:
        return None

    if isinstance(parsed, dt.datetime):
        if (parsed.hour, parsed.minute, parsed.second, parsed.microsecond) == (0, 0, 0, 0):
            return parsed.date().isoformat()
        return parsed.isoformat()

    return parsed.isoformat()


def _looks_like_tabular(text):
    lines = text.splitlines()
    if not lines:
        return False
    first = lines[0]
    return any(separator in first for separator in [",", "\t", ";"])


def _has_header(text):
    try:
        sample = text[:4096]
        csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";"])
        return csv.Sniffer().has_header(sample)
    except Exception:
        return False


def _determine_title(data):
    address = str(data.get("Property address", "")).strip()
    unit = str(data.get("Unit number", "")).strip()

    if address:
        if unit:
            return f"{address} Unit {unit}"
        return address

    complainant = str(data.get("Complainant name", "")).strip()
    if complainant:
        return complainant

    association = str(data.get("Association/community name", "")).strip()
    if association:
        return association

    for value in data.values():
        if value:
            return str(value)

    return "Unnamed record"


def _determine_status(data):
    raw_status = str(data.get("Status", "")).strip()

    if raw_status in STATUSES:
        return raw_status

    if raw_status and ":" in raw_status:
        candidate = raw_status.split(":", 1)[0].strip()
        if candidate in STATUSES:
            return candidate

    known_canonical_keys = set(FIELD_ALIASES.keys()) & set(data.keys())
    if known_canonical_keys:
        if not data.get("Property address") or not data.get("Violation description"):
            return "Missing"

    return "New"


def _row_to_record(data):
    mapped = {}
    for key, value in data.items():
        canonical = ALIAS_TO_FIELD.get(key)
        if canonical:
            if canonical not in mapped:
                mapped[canonical] = value
            else:
                mapped[canonical] = f"{mapped[canonical]}, {value}"
        else:
            mapped[key] = value

    return {
        "title": _determine_title(mapped),
        "status": _determine_status(mapped),
        "details": {k: v for k, v in mapped.items() if k not in ("Status", "Due date")},
        "due_date": _due_date_value(mapped.get("Due date")),
    }


def _parse_tabular(text):
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except Exception:
        return []

    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return []

    first_row = rows[0]
    normalized_first = [_normalize_key(cell) for cell in first_row]

    has_header = False
    if any(cell in ALIAS_TO_FIELD for cell in normalized_first):
        has_header = True
    else:
        has_header = _has_header(text)

    if has_header:
        header_row = first_row
        data_rows = rows[1:]
    else:
        header_row = [f"field_{i}" for i in range(len(first_row))]
        data_rows = rows

    header = [_normalize_key(cell) for cell in header_row]
    records = []

    for row in data_rows:
        if not any(cell.strip() for cell in row):
            continue

        row_data = {}
        for idx, cell in enumerate(row):
            if idx < len(header):
                row_data[header[idx]] = cell.strip()
            else:
                row_data[f"field_{idx}"] = cell.strip()

        if row_data:
            records.append(_row_to_record(row_data))

    return records


def _parse_plain_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    data = {}

    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            canonical = ALIAS_TO_FIELD.get(_normalize_key(key))
            if canonical:
                if canonical not in data:
                    data[canonical] = value.strip()
                else:
                    data[canonical] = f"{data[canonical]}; {value.strip()}"

    if data:
        return [_row_to_record(data)]

    if lines:
        return [{
            "title": lines[0][:80],
            "status": "New",
            "details": {"raw_text": text},
            "due_date": None,
        }]

    return []


def _parse_text_to_records(text):
    text = text.strip()
    if not text:
        return []

    if _looks_like_tabular(text):
        return _parse_tabular(text)

    return _parse_plain_text(text)


def _extract_text_from_pdf(file_bytes):
    if not file_bytes.startswith(b"%PDF"):
        return None

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages)
        return text if text.strip() else None
    except Exception:
        return None


def _extract_text_from_excel(file_bytes):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        rows = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                rows.append("\t".join("" if cell is None else str(cell) for cell in row))
        text = "\n".join(rows)
        return text if text.strip() else None
    except Exception:
        return None


def _llm_extract(text):
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return []

    try:
        from openai import OpenAI
    except Exception:
        return []

    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

    system_prompt = (
        "You extract structured HOA violation records from text. "
        "Return ONLY a JSON array of objects. Each object must have these keys: title, status, details, due_date. "
        "The title field MUST be the primary entity the buyer tracks — for HOA violations, use the property address and unit number if available, otherwise the complainant or owner name — NEVER the document type or category. "
        "status must be exactly one of: New, Missing, Valid, Notice Sent, In Cure, Expired, Fine Issued, Flagged, Closed, Void. "
        "due_date must be an ISO-8601 string or null. "
        "details is an object with all other extracted fields from the input, but must NOT contain due_date. "
        "Fields to extract include: Received timestamp, Received via, Complainant name, Complainant email, Complainant phone, Association/community name, Property address, Unit number, Violation category, Violation description, Photo evidence file reference(s), Incident date, Reporter type."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            temperature=0,
        )
        content = response.choices[0].message.content
        content = content.strip()

        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed = [parsed]

        return [item for item in parsed if isinstance(item, dict)]
    except Exception:
        return []


def process_file(file_bytes: bytes) -> list[dict]:
    if not file_bytes:
        return []

    text = None

    if file_bytes[:4] == b"%PDF":
        text = _extract_text_from_pdf(file_bytes)

    if text is None:
        text = _extract_text_from_excel(file_bytes)

    if text is None:
        text = file_bytes.decode("utf-8", errors="ignore")

    if not text.strip():
        return []

    records = _parse_text_to_records(text)

    if not records:
        records = _llm_extract(text)

    normalized_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        details = record.get("details", {})
        if not isinstance(details, dict):
            details = {}

        if "due_date" in details:
            del details["due_date"]

        normalized = {
            "title": str(record.get("title", "")),
            "status": str(record.get("status", "New")),
            "details": details,
            "due_date": _due_date_value(record.get("due_date")),
        }

        if normalized["status"] not in STATUSES:
            normalized["status"] = "New"

        normalized_records.append(normalized)

    return normalized_records
