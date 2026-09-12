"""
Conector a Remotive (remotive.com) — remoto worldwide. API pública, sin key.
Filtramos por ubicación a las abiertas para LatAm (worldwide/americas/latam/…).
"""
import json
import urllib.parse
import urllib.request

import pandas as pd

from .. import config as cfg
from ._common import parse_date, strip_html

API_URL = "https://remotive.com/api/remote-jobs"
_HEADERS = {"User-Agent": "FindJobIA/1.0"}

# Ubicaciones que sí aplican para alguien en LatAm/Colombia.
_LATAM_OK = (
    "worldwide", "anywhere", "latam", "latin america", "americas",
    "south america", "colombia",
)


def _latam_friendly(location: str) -> bool:
    loc = (location or "").lower()
    return not loc or any(k in loc for k in _LATAM_OK)


def _request(search: str, limit: int) -> dict:
    params = {"search": search, "limit": limit}
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=_HEADERS), timeout=25) as r:
        return json.load(r)


def fetch(terms=None, limit=None) -> pd.DataFrame:
    terms = terms if terms is not None else cfg.SEARCH_TERMS
    limit = limit or cfg.RESULTS_WANTED

    rows = []
    for term in terms:
        try:
            data = _request(term, limit)
        except Exception:  # noqa: BLE001
            continue
        for j in data.get("jobs", []):
            location = j.get("candidate_required_location") or ""
            if not _latam_friendly(location):
                continue
            url, title = j.get("url"), j.get("title")
            if not url or not title:
                continue
            rows.append({
                "job_url": url,
                "site": "remotive",
                "search_term": term,
                "title": title,
                "company": j.get("company_name") or "",
                "location": location,
                "is_remote": True,
                "job_type": j.get("job_type") or "",
                "date_posted": parse_date(j.get("publication_date")),
                "description": strip_html(j.get("description")),
                "company_logo": j.get("company_logo") or j.get("company_logo_url") or "",
                "company_industry": j.get("category") or "",
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["job_url"]).reset_index(drop=True)
