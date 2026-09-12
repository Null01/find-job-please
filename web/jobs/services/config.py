"""
Filtros "quemados" de la búsqueda. Los usa el servicio de scraping tanto desde
el botón web como desde `manage.py sync_jobs`.

Afinado para: remoto, LatAm/Colombia y ofertas recientes (< 48 h).
"""

# Roles a buscar (una búsqueda por término).
SEARCH_TERMS = [
    "backend developer",
    "full stack developer",
    "software engineer",
]

# Bolsas soportadas por JobSpy. linkedin = más fiable para remoto.
SITES = ["linkedin", "indeed"]

# Radicado en Colombia, remoto abierto a LatAm.
LOCATION = "Colombia"
IS_REMOTE = True
COUNTRY_INDEED = "colombia"

# Ventana de frescura: SOLO ofertas de las últimas 48 horas (2 días).
HOURS_OLD = 48

# Ofertas que pide cada término/bolsa (pool antes de filtrar por fecha).
RESULTS_WANTED = 20

# Tope por plataforma (se guardan las más recientes de cada una).
PER_SOURCE_MAX = 15

# Tope TOTAL de resultados por sincronización (se guardan los más recientes).
MAX_RESULTS = 30

# Tipo de contrato (None = cualquiera).
JOB_TYPE = None

# Palabras que suben el match_score.
KEYWORDS_BOOST = [
    "python", "typescript", "react", "node", "aws", "docker",
    "latam", "latin america", "colombia", "remote", "worldwide", "anywhere",
]
