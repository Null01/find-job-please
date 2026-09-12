"""
Servicio de scraping: obtiene ofertas desde JobSpy y calcula el match_score.

Función pura de datos (devuelve un DataFrame), sin tocar la base de datos —
del guardado se encarga `importer`.
"""
import pandas as pd

from . import config as cfg


def score_text(title: str, description: str, company: str, keywords) -> int:
    """Cuenta cuántas keywords aparecen en el texto de la oferta."""
    haystack = f"{title} {description} {company}".lower()
    return sum(1 for kw in keywords if kw.lower() in haystack)


def score(row: pd.Series, keywords=None) -> int:
    """Igual que score_text pero desde una fila (Series) del DataFrame."""
    keywords = keywords if keywords is not None else cfg.KEYWORDS_BOOST
    return score_text(
        str(row.get("title", "")),
        str(row.get("description", "")),
        str(row.get("company", "")),
        keywords,
    )


def fetch_jobs(terms=None, sites=None, location=None, country=None,
               results=None, hours=None, remote=None) -> pd.DataFrame:
    """Scrapea todos los términos y devuelve un DataFrame único (deduplicado)."""
    from jobspy import scrape_jobs  # import perezoso: acelera el arranque de Django

    terms = terms if terms is not None else cfg.SEARCH_TERMS
    sites = sites if sites is not None else cfg.SITES
    location = location if location is not None else cfg.LOCATION
    country = country if country is not None else cfg.COUNTRY_INDEED
    results = results if results is not None else cfg.RESULTS_WANTED
    hours = hours if hours is not None else cfg.HOURS_OLD
    remote = cfg.IS_REMOTE if remote is None else remote

    frames = []
    for term in terms:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                google_search_term=f"{term} remote jobs",
                location=location,
                is_remote=remote,
                job_type=cfg.JOB_TYPE,
                results_wanted=results,
                hours_old=hours,
                country_indeed=country,
                description_format="markdown",
                verbose=0,
            )
        except Exception:  # noqa: BLE001 - un término que falla no tumba el resto
            continue
        if df is not None and not df.empty:
            df["search_term"] = term
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    jobs = pd.concat(frames, ignore_index=True)
    col = "job_url" if "job_url" in jobs.columns else "title"
    return jobs.drop_duplicates(subset=[col]).reset_index(drop=True)
