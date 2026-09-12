"""
Servicio de importación: hace upsert de un DataFrame de ofertas a la BD.

Reutilizable por el scraping en vivo (JobSpy → BD) o por cualquier otra fuente
que produzca un DataFrame con las columnas esperadas.
"""
import math

import pandas as pd

from ..models import Job

# Columnas del DataFrame que se copian al modelo.
_COPY_FIELDS = (
    "site", "search_term", "title", "company", "location", "is_remote",
    "job_type", "date_posted", "min_amount", "max_amount", "currency",
    "description", "job_url_direct", "company_url", "company_logo",
    "company_industry", "company_num_employees",
)

# Campos de texto del modelo (None -> "", no aceptan NULL).
_TEXT_FIELDS = (
    "title", "company", "location", "site", "job_type", "currency",
    "search_term", "description", "job_url_direct", "company_url",
    "company_logo", "company_industry", "company_num_employees",
)


def _clean(value):
    """Normaliza NaN/None de pandas a algo que Django acepte."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def upsert_jobs(df: pd.DataFrame, owner, score_fn=None) -> dict:
    """Inserta/actualiza cada fila del DataFrame para un dueño.

    Devuelve {created, updated, skipped}. No pisa los campos de seguimiento
    (status, applied_at, is_favorite, notes), porque no están en `defaults`.
    """
    if df is None or df.empty or "job_url" not in df.columns:
        return {"created": 0, "updated": 0, "skipped": 0}

    created = updated = skipped = 0
    for _, row in df.iterrows():
        url = _clean(row.get("job_url"))
        title = _clean(row.get("title"))
        if not url or not title:
            skipped += 1
            continue

        fields = {}
        for col in _COPY_FIELDS:
            if col in df.columns:
                fields[col] = _clean(row.get(col))
        for f in _TEXT_FIELDS:
            fields[f] = "" if fields.get(f) is None else str(fields[f])

        if score_fn is not None:
            fields["match_score"] = score_fn(row)
        elif "match_score" in df.columns:
            fields["match_score"] = _clean(row.get("match_score")) or 0

        _, was_created = Job.objects.update_or_create(
            owner=owner, job_url=str(url), defaults=fields
        )
        created += was_created
        updated += not was_created

    return {"created": created, "updated": updated, "skipped": skipped}
