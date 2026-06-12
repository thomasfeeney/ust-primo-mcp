"""Client for the UST Primo VE discovery API (CLIC/MnPALS).

Wraps the unauthenticated public search endpoint that backs
librarysearch.stthomas.edu and normalizes Primo's PNX records into
compact dictionaries suitable for an LLM tool result.

Two scopes are exposed:
  - "ust"               -> Primo scope MyInstitution (UST's own catalog records only)
  - "ust_plus_articles" -> Primo scope MyInst_and_CI (blends in Ex Libris's
                           proprietary Central Discovery Index; pending license
                           review, so not the default)
"""

from __future__ import annotations

import re
from typing import Any

import httpx

DISCOVERY_HOST = "https://librarysearch.stthomas.edu"
SEARCH_PATH = "/primaws/rest/pub/pnxs"
VID = "01CLIC_STTHOMAS:MNPALS"

SCOPES = {
    "ust": "MyInstitution",
    "ust_plus_articles": "MyInst_and_CI",
}

FIELDS = {"any", "title", "creator", "subject"}
_FIELD_TO_PRIMO = {"any": "any", "title": "title", "creator": "creator", "subject": "sub"}

MAX_LIMIT = 25

_HEADERS = {
    "User-Agent": "ust-primo-mcp/0.1 (proof of concept; thomas.feeney@stthomas.edu)",
    "Accept": "application/json",
}

# Primo appends "$$Q..." (and similar $$-prefixed metadata) to display values.
_DOLLAR_TAG = re.compile(r"\$\$[A-Z].*$")


def _clean(value: Any) -> str | None:
    """Return the first string of a Primo display field, stripped of $$ tags."""
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str):
        return None
    return _DOLLAR_TAG.sub("", value).strip() or None


def _clean_list(value: Any, cap: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value[:cap]:
        c = _clean(v)
        if c:
            out.append(c)
    return out


def _permalink(doc: dict) -> str | None:
    control = doc.get("pnx", {}).get("control", {})
    recordid = _clean(control.get("recordid"))
    if not recordid:
        return None
    context = doc.get("context", "L")
    return (
        f"{DISCOVERY_HOST}/discovery/fulldisplay"
        f"?docid={recordid}&context={context}&vid={VID}"
    )


def _availability(doc: dict) -> dict:
    delivery = doc.get("delivery", {}) or {}
    out: dict[str, Any] = {}
    status = delivery.get("availability")
    if isinstance(status, list) and status:
        out["status"] = status[0]
    best = delivery.get("bestlocation")
    if isinstance(best, dict):
        loc_bits = [
            best.get("mainLocation"),
            best.get("subLocation"),
            best.get("callNumber"),
        ]
        loc = " — ".join(str(b) for b in loc_bits if b)
        if loc:
            out["location"] = loc
    services = delivery.get("electronicServices")
    if isinstance(services, list) and services:
        out["online"] = True
    return out


def normalize_record(doc: dict, full: bool = False) -> dict:
    """Flatten one Primo PNX document into a compact, LLM-friendly dict."""
    pnx = doc.get("pnx", {}) or {}
    display = pnx.get("display", {}) or {}
    control = pnx.get("control", {}) or {}

    record = {
        "id": _clean(control.get("recordid")),
        "title": _clean(display.get("title")),
        "creator": _clean(display.get("creator")) or _clean(display.get("contributor")),
        "type": _clean(display.get("type")),
        "date": _clean(display.get("creationdate")),
        "publisher": _clean(display.get("publisher")),
        "language": _clean(display.get("language")),
        "source": "UST catalog" if doc.get("context") == "L" else "Central Discovery Index",
        "permalink": _permalink(doc),
    }
    record.update(_availability(doc))

    if full:
        record["contributors"] = _clean_list(display.get("contributor"))
        record["subjects"] = _clean_list(display.get("subject"))
        record["description"] = _clean(display.get("description"))
        record["format"] = _clean(display.get("format"))
        record["isbn"] = _clean(display.get("identifier"))
        record["edition"] = _clean(display.get("edition"))
        record["series"] = _clean(display.get("ispartof"))

    return {k: v for k, v in record.items() if v not in (None, [], "")}


async def search(
    query: str,
    field: str = "any",
    scope: str = "ust",
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Search the catalog; returns counts plus normalized records."""
    if field not in FIELDS:
        raise ValueError(f"field must be one of {sorted(FIELDS)}")
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {sorted(SCOPES)}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))

    params = [
        ("vid", VID),
        ("tab", "Everything"),
        ("scope", SCOPES[scope]),
        ("q", f"{_FIELD_TO_PRIMO[field]},contains,{query}"),
        ("offset", str(offset)),
        ("limit", str(limit)),
        ("lang", "en"),
    ]
    async with httpx.AsyncClient(headers=_HEADERS, timeout=30) as client:
        resp = await client.get(f"{DISCOVERY_HOST}{SEARCH_PATH}", params=params)
        resp.raise_for_status()
        data = resp.json()

    info = data.get("info", {}) or {}
    docs = data.get("docs", []) or []
    result = {
        "query": query,
        "field": field,
        "scope": scope,
        "total_ust_records": info.get("totalResultsLocal"),
        "offset": offset,
        "returned": len(docs),
        "records": [normalize_record(d) for d in docs],
    }
    if scope == "ust_plus_articles":
        result["total_central_index_records"] = info.get("totalResultsPC")
    return result


async def get_record(record_id: str) -> dict:
    """Fetch one record by its Primo record ID (e.g. 'alma9910...' or bare MMS ID)."""
    bare = record_id.removeprefix("alma")
    params = [
        ("vid", VID),
        ("tab", "Everything"),
        ("scope", SCOPES["ust_plus_articles"]),
        ("q", f"any,contains,{bare}"),
        ("offset", "0"),
        ("limit", "3"),
        ("lang", "en"),
    ]
    async with httpx.AsyncClient(headers=_HEADERS, timeout=30) as client:
        resp = await client.get(f"{DISCOVERY_HOST}{SEARCH_PATH}", params=params)
        resp.raise_for_status()
        docs = resp.json().get("docs", []) or []
    for doc in docs:
        rid = _clean(doc.get("pnx", {}).get("control", {}).get("recordid")) or ""
        if bare in rid or record_id == rid:
            return normalize_record(doc, full=True)
    return {"error": f"No record found for ID {record_id!r}."}
