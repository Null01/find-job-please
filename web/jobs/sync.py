"""
Orquesta la sincronización de ofertas desde la web.

La lógica pesada (scraping + ranking + upsert) vive en `jobs.services`.
Aquí solo está el manejo de estado y el hilo en segundo plano para que el
botón de la web no bloquee la petición.
"""
import threading
from datetime import datetime, timezone

import pandas as pd

from .services import importer, scraper
from .services.connectors import getonbrd, jobicy, remotive, torre

# Estado compartido de la última/actual sincronización.
_lock = threading.Lock()
_status = {
    "running": False,
    "message": "Aún no has sincronizado.",
    "created": 0,
    "updated": 0,
    "finished_at": None,
    "error": None,
}


def get_status() -> dict:
    with _lock:
        return dict(_status)


# Fuentes de ofertas. Cada una devuelve un DataFrame en el esquema común.
# Agregar una plataforma nueva = añadir su fetch aquí.
_SOURCES = [
    ("JobSpy (LinkedIn/Indeed)", scraper.fetch_jobs),
    ("Get on Board", getonbrd.fetch),
    ("Jobicy", jobicy.fetch),
    ("Torre", torre.fetch),
    ("Remotive", remotive.fetch),
]


def _recent_top(df, cutoff, limit):
    """Deja solo ofertas dentro de la ventana (por fecha) y las N más recientes."""
    df = df.copy()
    df["_d"] = pd.to_datetime(df.get("date_posted"), errors="coerce", utc=True)
    df = df[df["_d"].notna() & (df["_d"] >= cutoff)]
    return df.sort_values("_d", ascending=False).head(limit).drop(columns="_d")


def run_sync(owner) -> dict:
    """Sincroniza todas las fuentes para un dueño. Devuelve {created, updated}."""
    from .services import config as cfg, dedup

    # Solo ofertas de las últimas HOURS_OLD horas (2 días).
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=cfg.HOURS_OLD)

    frames = []
    for _, fetch in _SOURCES:
        try:
            df = fetch()
        except Exception:  # noqa: BLE001 - una fuente que falla no tumba el resto
            continue
        if df is None or df.empty:
            continue
        # Por plataforma: recientes (≤48h) y como máximo PER_SOURCE_MAX.
        df = _recent_top(df, cutoff, cfg.PER_SOURCE_MAX)
        if not df.empty:
            frames.append(df)

    if not frames:
        return {"created": 0, "updated": 0, "skipped": 0}

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"]).reset_index(drop=True)
    # Colapsa duplicados lógicos (misma oferta por ciudad/bolsa) antes de guardar.
    combined = dedup.dedup_frame(combined)

    # Acota al total a las MAX_RESULTS más recientes.
    combined = combined.assign(
        _d=pd.to_datetime(combined["date_posted"], errors="coerce", utc=True)
    ).sort_values("_d", ascending=False, na_position="last").drop(columns="_d")
    combined = combined.head(cfg.MAX_RESULTS).reset_index(drop=True)

    # 1) Guarda. 2) Dedup en BD (cruza sincronizaciones, preserva seguimiento).
    result = importer.upsert_jobs(combined, owner)
    dedup.dedup_owner_jobs(owner)

    # 3) Rankea con la estrategia activa (sobre el set ya sin duplicados).
    from .services.rankers import get_active_ranker
    get_active_ranker().rank(owner)
    return result


def _worker(owner):
    try:
        result = run_sync(owner)
        now = datetime.now(timezone.utc).strftime("%H:%M")
        with _lock:
            _status.update(
                running=False, error=None,
                created=result["created"], updated=result["updated"],
                finished_at=now,
                message=(f"Sincronizado a las {now}: "
                         f"{result['created']} nuevas, {result['updated']} actualizadas."),
            )
    except Exception as e:  # noqa: BLE001
        with _lock:
            _status.update(running=False, error=str(e),
                           message=f"Error en la sincronización: {e}")


def start_background_sync(owner) -> bool:
    """Arranca la sincronización en un hilo. False si ya hay una corriendo."""
    with _lock:
        if _status["running"]:
            return False
        _status.update(running=True, error=None,
                       message="Sincronizando… esto tarda ~1–2 min.")
    threading.Thread(target=_worker, args=(owner,), daemon=True).start()
    return True
