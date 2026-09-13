# FindJob IA

Buscador de trabajo remoto en tech para LatAm. Agrega ofertas desde
[JobSpy](https://github.com/speedyapply/JobSpy) (LinkedIn + Indeed) y
[Get on Board](https://www.getonbrd.com), las rankea contra tu stack y las sirve
en una web (Django + PostgreSQL) donde puedes listarlas, filtrarlas, seguir tus
postulaciones y **sincronizar con un botón**.

## Arranque

> **Cómo correr la app.** Requisito único: tener **Docker Desktop instalado y
> abierto**. No necesitas Python ni nada más: todo corre en contenedores.

### Levantar en local vs remoto

**Local** — Postgres en un contenedor (todo en Docker, sin dependencias externas):

```bash
cp .env.example .env          # rellena POSTGRES_* y DJANGO_SECRET_KEY
docker compose up --build -d  # app en http://localhost:8000/
```

**Remoto** — BD gestionada (Supabase) con los secretos inyectados por Infisical:

```bash
# DATABASE_URL (de Supabase) vive en Infisical, no en el repo.
# Si está definida, la app la usa (con TLS) e IGNORA el Postgres local.
infisical run --env=prod -- docker compose up -d
```

Guía completa de producción (Supabase + Infisical + rotación) en **[DEPLOY.md](DEPLOY.md)**.

---

Desde la raíz del proyecto (`find-job-please/`):

```bash
docker compose up --build -d
```

Eso levanta dos contenedores: `db` (PostgreSQL) y `web` (Django). Luego abre:

- **App / ofertas:**  http://localhost:8000/
- **Panel admin:**    http://localhost:8000/admin/

La primera vez la base está vacía: pulsa **⟳ Sincronizar** en la web (tarda
~1–2 min) para traer ofertas. ¡Listo!

Otros comandos útiles:

```bash
docker compose logs -f web     # ver logs de la app
docker compose down            # parar todo (los datos persisten en el volumen pgdata)
docker compose up -d           # volver a levantar (sin --build si no cambió el Dockerfile)
```

### Desarrollo: hooks de seguridad (pre-commit)

Este repo usa [pre-commit](https://pre-commit.com) + [gitleaks](https://github.com/gitleaks/gitleaks)
para evitar subir secretos por error. **Tras clonar el repo, córrelo una vez:**

```bash
pre-commit install
```

Requisitos: tener `pre-commit` y `gitleaks` instalados (en macOS: `brew install pre-commit gitleaks`).
Desde entonces, cada `git commit` escanea lo que vas a subir y **bloquea** secretos y archivos
`.env`. Para un escaneo manual: `pre-commit run --all-files`.

Antes de arrancar, copia la plantilla de entorno y rellena tus valores (el `.env` real está en
`.gitignore` y **nunca** debe commitearse):

```bash
cp .env.example .env
```

Como red de seguridad, el workflow `.github/workflows/secret-scan.yml` repite el escaneo en
GitHub Actions, así que la protección aplica aunque alguien no tenga los hooks locales.

**Convención de variables:** todos los secretos/config llevan **prefijo de espacio de nombres**
(`POSTGRES_*`, `DJANGO_*`, `DB_*`, `DATABASE_URL`) y **la configuración de negocio empieza por
`BUSINESS_*`** (p. ej. `BUSINESS_RANKER_STRATEGY`, `BUSINESS_EMBEDDING_MODEL`). Facilita
agruparlos y escanearlos en el gestor de secretos.

## Sincronizar ofertas

El botón **⟳ Sincronizar** busca en todas las fuentes (JobSpy + Get on Board) con
los filtros de `web/jobs/services/config.py` (remoto, LatAm/Colombia, últimas
48 h), deduplica y guarda directo en Postgres. Corre en segundo plano y la vista
se recarga sola.

Equivalente por consola:

```bash
docker compose exec web python manage.py sync_jobs
```

## Cuenta, CV y perfil

La app tiene **login (correo + contraseña)**: te registras en `/register/`, inicias
sesión en `/login/`, y todas las vistas requieren estar autenticado. Cada usuario
(`User` de Django) está vinculado a un `Owner` (1:1), y **sus CVs y ofertas cuelgan
de ese Owner** — cada quien ve solo lo suyo. Tu **perfil** (`/perfil/`) muestra tu
cuenta, tu CV activo, las keywords detectadas y tus métricas.

Botón **📄 Subir CV** (barra superior) → modal para subir el CV en PDF de tu cuenta.
El archivo se guarda en `web/media/cv/<correo>/<archivo>.pdf`. Según tus ofertas:

- **Ya registrado (con ofertas):** se muestran sus ofertas guardadas.
- **Nuevo (sin ofertas):** pide **sincronizar desde cero** para traerlas.

Luego **Analizar documento** extrae tus tecnologías (con `pypdf` + vocabulario en
`services/cv.py`) y **recalcula el match de tus ofertas**. Los próximos
`Sincronizar` (botón o `manage.py sync_jobs`) usan esas palabras clave. Cada
dueño ve y sincroniza solo lo suyo.

### Automatizar (macOS, opcional)

Sincroniza solo cada mañana con `launchd` (requiere el stack levantado):

```bash
cp com.andres.findjob.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.andres.findjob.plist
launchctl start com.andres.findjob      # probar ya, sin esperar
```

Quitarlo: `launchctl unload ~/Library/LaunchAgents/com.andres.findjob.plist`

## Arquitectura

```
docker-compose.yml          db (Postgres 16) + web (Django)
web/
├── config/                 proyecto Django (settings, urls, wsgi)
└── jobs/                   app principal
    ├── models.py           Owner (dueño por correo), CV, Job (oferta + seguimiento)
    ├── views.py            lista, detalle, endpoints de sync/estado/notas
    ├── sync.py             orquesta la sync (estado + hilo en segundo plano)
    ├── services/           ← lógica reutilizable
    │   ├── config.py       filtros de búsqueda "quemados"
    │   ├── scraper.py      JobSpy (LinkedIn/Indeed) → DataFrame + ranking
    │   ├── importer.py     DataFrame → upsert en la BD
    │   ├── cv.py           PDF → texto + keywords
    │   ├── dedup.py        colapsa duplicados lógicos (empresa + título)
    │   ├── rankers/        estrategias de match (conectables por config)
    │   │   ├── keyword.py     léxico (keywords del CV) → 0–100
    │   │   └── embeddings.py  semántico local (E5 multilingüe + híbrido)
    │   └── connectors/     otras plataformas (una = un archivo)
    │       ├── getonbrd.py Get on Board (remoto LatAm/Colombia)
    │       ├── jobicy.py   Jobicy (geo=latam)
    │       ├── torre.py    Torre (nativa Colombia/LatAm)
    │       └── remotive.py Remotive (worldwide, filtrado LatAm)
    ├── management/commands/sync_jobs.py   sync por consola/cron
    └── templates/jobs/     job_list.html, job_detail.html
```

El **servicio** (`jobs/services/`) concentra scraping, ranking e importación, y lo
usan tanto el botón web como el comando de consola. Un re-sync **no pisa** tu
seguimiento (estado, favoritos, notas).

### Ranking del match (conectable)

El puntaje de match (0–100) lo calcula una estrategia **conectable** vía la
variable `BUSINESS_RANKER_STRATEGY` en `.env` (cambiar y reiniciar el web):

- **`embeddings`** (por defecto) — **semántico local, offline, sin API key**.
  Usa un bi-encoder multilingüe (E5) + señal léxica (híbrido denso-sparse) y
  cachea el vector de cada oferta. Modelo configurable con `BUSINESS_EMBEDDING_MODEL`
  (`intfloat/multilingual-e5-base` por defecto; `...-e5-large` para más calidad).
- **`keyword`** — léxico simple (cuenta keywords del CV). Rápido, sin modelos.

La primera corrida descarga el modelo (~1 GB) al volumen `hf_cache`; luego los
re-rankings son de segundos. Agregar una estrategia (p. ej. LLM) = un archivo en
`web/jobs/services/rankers/` + una entrada en su registro.

### Ajustar la búsqueda

Edita `web/jobs/services/config.py`:

- `SEARCH_TERMS`: roles a buscar (una búsqueda por término).
- `SITES`: `linkedin` es el más fiable; `indeed` exige `COUNTRY_INDEED` válido.
- `LOCATION` / `IS_REMOTE`: enfoque geográfico y remoto.
- `HOURS_OLD`: ventana de frescura (48 = últimos 2 días).
- `PER_SOURCE_MAX`: tope por plataforma (15 = las 15 más recientes de cada una).
- `MAX_RESULTS`: tope total por sync (30 = las 30 más recientes).
- `KEYWORDS_BOOST`: palabras que suben el `match_score`.

Crear usuario para el admin / futuro login:

```bash
docker compose exec web python manage.py createsuperuser
```

## Roadmap

- [x] Scraping + ranking por keywords (JobSpy).
- [x] UI web (Django + Postgres + Docker) para listar/filtrar.
- [x] Botón de sincronizar: JobSpy escribe directo a Postgres.
- [x] Seguimiento (estado, favoritos, notas), vista de detalle y enriquecimiento.
- [x] Consolidación: lógica reutilizable movida a `jobs/services/`.
- [x] Más plataformas vía conectores: **Get on Board, Jobicy, Torre, Remotive** (remoto LatAm).
- [ ] Vista "Nuevas" (ofertas desde el último sync, usando `created_at`).
- [ ] Aún más plataformas (Himalayas, RemoteOK, WeWorkRemotely…).
- [x] Subir CV (PDF) por correo y extraer keywords para personalizar el match.
- [x] Multi-dueño: ofertas vinculadas al correo del CV; nuevo correo pide sync.
- [x] Login (correo + contraseña), registro y sección de perfil; datos por usuario.
- [x] Deduplicar la misma oferta repetida por ciudad/bolsa (antes de rankear).
- [x] Ranking semántico local (embeddings E5 + híbrido), conectable por config.
- [ ] Estrategia de ranking con LLM (híbrido) como opción conectable.

## Nota legal

Este proyecto solo **agrega y filtra** ofertas públicas. Automatizar el envío de
postulaciones en LinkedIn viola sus Términos de Servicio y puede llevar al baneo
de la cuenta; por eso aquí no se hace auto-apply.
