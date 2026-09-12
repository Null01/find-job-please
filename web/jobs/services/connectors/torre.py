"""
Conector a Torre (torre.co) — plataforma nativa de Colombia/LatAm.
API de búsqueda por POST (no oficial). Filtramos remoto.
"""
import json
import urllib.request

import pandas as pd

from .. import config as cfg
from ._common import parse_date, strip_html

API_URL = "https://search.torre.co/opportunities/_search?offset=0&size=%d&aggregate=false"
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _request(term: str, size: int) -> dict:
    body = {"and": [
        {"skill/role": {"text": term, "experience": "potential-to-develop"}},
        {"remote": {"term": True}},
    ]}
    req = urllib.request.Request(
        API_URL % size, data=json.dumps(body).encode(), headers=_HEADERS, method="POST"
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def fetch(terms=None, size=None) -> pd.DataFrame:
    terms = terms if terms is not None else cfg.SEARCH_TERMS
    size = size or cfg.RESULTS_WANTED

    rows = []
    for term in terms:
        try:
            data = _request(term, size)
        except Exception:  # noqa: BLE001
            continue
        for r in data.get("results", []):
            oid, title = r.get("id"), r.get("objective")
            if not oid or not title:
                continue
            orgs = r.get("organizations") or []
            org = orgs[0] if orgs else {}
            comp = (r.get("compensation") or {})
            comp = comp.get("data") or {} if isinstance(comp, dict) else {}
            min_a, max_a = comp.get("minAmount") or 0, comp.get("maxAmount") or 0
            locs = r.get("locations") or []
            commitment = r.get("commitment") or {}
            job_type = commitment.get("code") if isinstance(commitment, dict) else str(commitment)

            rows.append({
                "job_url": f"https://torre.co/jobs/{oid}",
                "site": "torre",
                "search_term": term,
                "title": title,
                "company": org.get("name") or "",
                "location": ", ".join(str(x) for x in locs) if locs else "Remoto",
                "is_remote": bool(r.get("remote")),
                "job_type": job_type or "",
                "date_posted": parse_date(r.get("created")),
                "min_amount": min_a or None,
                "max_amount": max_a or None,
                "currency": comp.get("currency", "") if (min_a or max_a) else "",
                "description": strip_html(r.get("tagline") or ""),
                "company_logo": org.get("picture") or "",
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["job_url"]).reset_index(drop=True)
