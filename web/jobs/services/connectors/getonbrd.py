"""
Conector a Get on Board (getonbrd.com) — la bolsa de empleo tech remoto más
fuerte de LatAm. Usa su API pública v0 (JSON:API, sin API key).

Docs: https://api.getonbrd.com  ·  Endpoint: /api/v0/search/jobs
"""
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from .. import config as cfg

API_URL = "https://www.getonbrd.com/api/v0/search/jobs"
_HEADERS = {"User-Agent": "FindJobIA/1.0 (+https://localhost)"}


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _to_date(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    except (TypeError, ValueError):
        return None


def _request(query: str, per_page: int) -> dict:
    params = {"query": query, "per_page": per_page, "expand": '["company"]'}
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def _row(job: dict, term: str, remote_only: bool):
    a = job.get("attributes", {})
    if remote_only and not a.get("remote"):
        return None

    url = (job.get("links") or {}).get("public_url")
    if not url or not a.get("title"):
        return None

    company = (a.get("company") or {}).get("data", {}).get("attributes", {})

    # Descripción legible: junta funciones + requisitos + beneficios, sin HTML.
    desc = " \n\n".join(filter(None, [
        _strip_html(a.get("functions")),
        _strip_html(a.get("description")),
        _strip_html(a.get("benefits")),
    ]))

    countries = a.get("countries") or []
    min_sal, max_sal = a.get("min_salary"), a.get("max_salary")

    return {
        "job_url": url,
        "site": "getonbrd",
        "search_term": term,
        "title": a.get("title") or "",
        "company": company.get("name") or "",
        "location": ", ".join(countries) if countries else "",
        "is_remote": bool(a.get("remote")),
        "job_type": (a.get("category_name") or ""),
        "date_posted": _to_date(a.get("published_at")),
        "min_amount": min_sal,
        "max_amount": max_sal,
        "currency": "USD" if (min_sal or max_sal) else "",
        "description": desc,
        "company_url": company.get("web") or "",
        "company_logo": company.get("logo") or "",
    }


def fetch(terms=None, per_page=None, remote_only=None) -> pd.DataFrame:
    """Trae ofertas de Get on Board para cada término y devuelve un DataFrame."""
    terms = terms if terms is not None else cfg.SEARCH_TERMS
    per_page = per_page or cfg.RESULTS_WANTED
    remote_only = cfg.IS_REMOTE if remote_only is None else remote_only

    rows = []
    for term in terms:
        try:
            data = _request(term, per_page)
        except Exception:  # noqa: BLE001 - un término que falla no tumba el resto
            continue
        for job in data.get("data", []):
            row = _row(job, term, remote_only)
            if row:
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["job_url"]).reset_index(drop=True)
