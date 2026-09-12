"""
Conector a Jobicy (jobicy.com) — remoto worldwide con filtro por región.
API pública v2, sin key. Usamos geo=latam para acotar a LatAm.
"""
import json
import urllib.parse
import urllib.request

import pandas as pd

from .. import config as cfg
from ._common import parse_date, strip_html

API_URL = "https://jobicy.com/api/v2/remote-jobs"
_HEADERS = {"User-Agent": "FindJobIA/1.0"}


def _request(tag: str, count: int) -> dict:
    params = {"count": count, "geo": "latam", "tag": tag}
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=_HEADERS), timeout=25) as r:
        return json.load(r)


def fetch(terms=None, count=None) -> pd.DataFrame:
    terms = terms if terms is not None else cfg.SEARCH_TERMS
    count = count or cfg.RESULTS_WANTED

    rows = []
    for term in terms:
        try:
            data = _request(term, count)
        except Exception:  # noqa: BLE001
            continue
        for j in data.get("jobs", []):
            url, title = j.get("url"), j.get("jobTitle")
            if not url or not title:
                continue
            job_type = j.get("jobType")
            if isinstance(job_type, list):
                job_type = ", ".join(job_type)
            rows.append({
                "job_url": url,
                "site": "jobicy",
                "search_term": term,
                "title": title,
                "company": j.get("companyName") or "",
                "location": j.get("jobGeo") or "",
                "is_remote": True,
                "job_type": job_type or "",
                "date_posted": parse_date(j.get("pubDate")),
                "description": strip_html(j.get("jobDescription") or j.get("jobExcerpt")),
                "company_logo": j.get("companyLogo") or "",
                "company_industry": j.get("jobIndustry") or "",
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["job_url"]).reset_index(drop=True)
