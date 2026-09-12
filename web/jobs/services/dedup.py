"""
Deduplicación de ofertas.

Más allá de la URL exacta, la misma oferta suele repetirse: por ciudad
("… - Bogotá", "… - Medellín"), por bolsa (LinkedIn + Indeed + Get on Board) o
con variantes de texto. Aquí se colapsan por una **clave lógica**:

    (empresa normalizada, núcleo del título)

El "núcleo del título" es el texto antes del primer separador (` - `, ` · `,
` | `, ` — `), donde suele ir la ciudad o el tipo de contrato. Así "Software
Engineer (Golang/TS/React) - Bogotá · Fully Remote" y "Software Engineer
(Golang/TS/React) - Contractor" caen en la misma clave, pero "Lead Software
Engineer …" (otro nivel) NO se mezcla.
"""
import re

_SEP = re.compile(r"\s+[-–—·|]\s+")
_COMPANY_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|corp|co|gmbh|srl|sas|s\.a\.s?|s\.a\.)\b\.?", re.I
)


def _norm_company(company: str) -> str:
    c = (company or "").lower()
    c = _COMPANY_SUFFIX.sub("", c)
    return re.sub(r"[^a-z0-9]+", " ", c).strip()


def _title_core(title: str) -> str:
    t = (title or "").lower()
    t = _SEP.split(t)[0]                      # texto antes del 1er separador
    t = re.sub(r"[^a-z0-9/+#. ]+", " ", t)    # conserva stack (c++, node.js, .net)
    return re.sub(r"\s+", " ", t).strip()


def logical_key(company: str, title: str) -> str:
    return f"{_norm_company(company)}||{_title_core(title)}"


def dedup_frame(df):
    """Colapsa duplicados lógicos en un DataFrame, dejando la fila más rica."""
    if df is None or df.empty or "title" not in df.columns:
        return df
    df = df.copy()

    def richness(row):
        score = 0
        if str(row.get("description", "") or "").strip():
            score += 4
        if str(row.get("job_url_direct", "") or "").strip():
            score += 2
        if bool(row.get("is_remote")):
            score += 1
        return score

    df["_key"] = df.apply(
        lambda r: logical_key(str(r.get("company", "")), str(r.get("title", ""))),
        axis=1,
    )
    df["_rich"] = df.apply(richness, axis=1)
    df = (
        df.sort_values("_rich", ascending=False)
        .drop_duplicates(subset="_key", keep="first")
        .drop(columns=["_key", "_rich"])
        .reset_index(drop=True)
    )
    return df


def _db_priority(job):
    """Orden de preferencia al conservar una fila de la BD (menor = se conserva)."""
    tracked = (job.status != "new") or job.is_favorite or bool(job.notes)
    return (
        0 if tracked else 1,                       # nunca perder seguimiento
        -len(job.description or ""),               # más descripción
        0 if job.job_url_direct else 1,            # con link directo
        -(job.date_posted.toordinal() if job.date_posted else 0),  # más reciente
    )


def dedup_owner_jobs(owner) -> int:
    """Elimina duplicados lógicos ya guardados de un dueño. Devuelve cuántos borró.

    Conserva la fila con seguimiento (estado/favorito/notas) si la hay; si no, la
    más completa.
    """
    from ..models import Job

    groups = {}
    for job in Job.objects.filter(owner=owner):
        groups.setdefault(logical_key(job.company, job.title), []).append(job)

    to_delete = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        rows.sort(key=_db_priority)
        to_delete.extend(rows[1:])

    ids = [j.id for j in to_delete]
    if ids:
        Job.objects.filter(id__in=ids).delete()
    return len(ids)
