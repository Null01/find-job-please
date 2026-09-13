# Arquitectura — FindJob IA

Buscador de trabajo remoto para LatAm/Colombia. Agrega ofertas de varias
plataformas, las deduplica, las rankea semánticamente contra tu CV y las sirve en
una web con login por usuario. Todo corre en Docker.

## Stack

| Capa | Tecnología |
|---|---|
| Web | Django 5 (auth, ORM, templates) |
| Base de datos | PostgreSQL 16 |
| Scraping | JobSpy (LinkedIn/Indeed) + conectores API |
| Ranking | Embeddings locales E5 multilingüe (sentence-transformers) o keywords |
| CV | pypdf (extracción de texto) |
| Orquestación | Docker Compose (`db` + `web`) |

---

## Diagrama de componentes

```mermaid
flowchart TB
    B["🌐 Navegador"]

    subgraph web["Contenedor web · Django"]
        direction TB
        V["Vistas<br/>auth · lista · detalle · sync · cv · acciones"]
        TPL["Templates<br/>HTML + JS"]
        M["Modelos<br/>User · Owner · CV · Job"]
        SY["sync<br/>orquestador + hilo background"]
        subgraph SVC["services"]
            direction TB
            SCR["scraper · JobSpy"]
            IMP["importer · upsert"]
            DED["dedup"]
            CVS["cv · PDF→keywords"]
            KW["ranker: keyword"]
            EMB["ranker: embeddings E5"]
            GOB["getonbrd"]
            JOB["jobicy"]
            TOR["torre"]
            REM["remotive"]
        end
    end

    DB[("PostgreSQL<br/>pgdata")]
    MED[("media<br/>CV PDFs")]
    HF[("hf_cache<br/>modelo E5")]

    LI["LinkedIn / Indeed"]
    APIS["GetOnBoard · Jobicy<br/>Torre · Remotive"]
    HFH["HuggingFace Hub"]

    B <-->|HTTP| V
    V --> TPL
    V --> M
    V --> CVS
    V --> SY
    SY --> SCR
    SY --> GOB
    SY --> JOB
    SY --> TOR
    SY --> REM
    SY --> DED
    SY --> IMP
    SY --> EMB
    SY -.-> KW
    SCR -->|scrape| LI
    GOB --> APIS
    JOB --> APIS
    TOR --> APIS
    REM --> APIS
    M --> DB
    IMP --> DB
    EMB --> HF
    EMB -.->|1ª vez| HFH
    CVS --> MED
```

---

## Modelo de datos

```mermaid
erDiagram
    USER ||--o| OWNER : "1:1"
    OWNER ||--o{ CV : "sube"
    OWNER ||--o{ JOB : "posee"

    USER {
        string username "= correo"
        string email
        string password
    }
    OWNER {
        int id PK
        int user_id FK "OneToOne, nullable"
        string email UK
        datetime created_at
    }
    CV {
        int id PK
        int owner_id FK
        string file "media/cv/<correo>/..."
        text text
        json keywords
        datetime analyzed_at
        bool is_active
    }
    JOB {
        int id PK
        int owner_id FK
        string job_url "único por owner"
        string title
        string company
        string location
        date date_posted
        int match_score "0-100"
        string status "new/applied/..."
        bool is_favorite
        text notes
        json embedding "cache E5"
    }
```

---

## Flujos por acción

### 1. Registro

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as Vista register
    participant DB as PostgreSQL
    U->>B: Correo + contraseña
    B->>V: POST /register/
    V->>V: Valida correo único + contraseña segura
    V->>DB: Crea User (username = correo)
    V->>DB: get_or_create Owner + enlaza user
    V->>B: login() + redirect a la lista
    B-->>U: Entra autenticado
```

### 2. Login

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as LoginView
    participant DB as PostgreSQL
    U->>B: Correo + contraseña
    B->>V: POST /login/
    V->>DB: authenticate(username = correo)
    alt Credenciales válidas
        V->>B: Cookie sessionid + redirect a la lista
    else Inválidas
        V->>B: Error "correo o contraseña incorrectos"
    end
```

### 3. Logout

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as LogoutView
    U->>B: Cerrar sesión
    B->>V: POST /logout/
    V->>B: Elimina sesión + redirect a /login/
```

### 4. Subir CV

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as Vista upload_cv
    participant FS as media (disco)
    participant DB as PostgreSQL
    U->>B: Elige PDF y "Subir CV"
    B->>B: Overlay bloqueante "Subiendo CV…"
    B->>V: POST /cv/upload/ (multipart)
    V->>V: Valida PDF + toma el Owner del usuario
    V->>FS: Guarda cv/<correo>/archivo.pdf
    V->>DB: Crea CV (is_active) y desactiva anteriores
    V-->>B: {ok, existing, job_count}
    B->>B: Quita overlay → "Analizar" o "Ver ofertas"
```

### 5. Analizar CV

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as Vista analyze_cv
    participant CVS as services.cv (pypdf)
    participant D as dedup
    participant R as ranker (embeddings E5)
    participant DB as PostgreSQL
    U->>B: "Analizar documento"
    B->>B: Overlay "Analizando CV y calculando match…"
    B->>V: POST /cv/<id>/analyze/
    V->>CVS: extract_text + extract_keywords
    CVS-->>V: texto + keywords
    V->>DB: Guarda text, keywords, analyzed_at
    V->>D: dedup_owner_jobs(owner)
    V->>R: rank(owner) — similitud CV ↔ ofertas
    R->>DB: match_score 0-100
    V-->>B: {keywords, rescored}
    B->>B: Muestra keywords y recarga
```

### 6. Sincronizar ofertas

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as sync_start / sync_status
    participant W as Hilo background
    participant SRC as Fuentes (JobSpy + 4 APIs)
    participant P as dedup + tope
    participant R as ranker
    participant DB as PostgreSQL
    U->>B: "Sincronizar"
    B->>B: Overlay "Sincronizando…"
    B->>V: POST /sync/
    V->>W: start_background_sync(owner)
    V-->>B: {running: true}
    par Trabajo en background
        W->>SRC: fetch() por fuente (≤48h, ≤15 c/u)
        SRC-->>W: DataFrames
        W->>P: dedup URL + lógico → tope 30 recientes
        W->>DB: upsert ofertas del owner
        W->>DB: dedup_owner_jobs
        W->>R: rank(owner)
        R->>DB: match_score
    and Polling
        loop cada 3s
            B->>V: GET /sync/status/
            V-->>B: {running, message}
        end
    end
    B->>B: running = false → recarga con lo nuevo
```

**Pipeline interno de la sincronización:**

```mermaid
flowchart LR
    A["Fuentes:<br/>JobSpy + GetOnBoard<br/>Jobicy + Torre + Remotive"] --> B["Por fuente:<br/>≤ 48h y ≤ 15 recientes"]
    B --> C["Combinar"]
    C --> D["Dedup por URL exacta"]
    D --> E["Dedup lógico<br/>empresa + título"]
    E --> F["Ordenar por fecha<br/>→ tope 30"]
    F --> G["Upsert en BD<br/>por owner"]
    G --> H["Dedup en BD<br/>preserva seguimiento"]
    H --> I["Ranking<br/>embeddings E5"]
    I --> J["match_score 0-100"]
```

### 7. Ver ofertas y detalle (filtros preservados)

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant L as Vista job_list
    participant D as Vista job_detail
    participant DB as PostgreSQL
    U->>B: Aplica filtros (búsqueda, bolsa, remoto, estado)
    B->>L: GET /?q&site&remote&status&page
    L->>DB: Filtra ofertas del owner + orden (tramo + fecha)
    L-->>B: Lista + enlaces al detalle con ?filtros
    U->>B: Clic en "Detalle"
    B->>D: GET /job/<id>/?filtros
    D-->>B: Detalle + "Volver" con ?filtros
    U->>B: "Volver" → misma lista, mismos filtros
```

### 8. Seguimiento: estado, favorito y notas

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as set_status / toggle_favorite / save_notes
    participant DB as PostgreSQL
    U->>B: Cambia estado / marca ★ / escribe notas
    B->>V: POST /job/<id>/(status|favorite|notes)/
    V->>V: Verifica que la oferta pertenece al owner
    V->>DB: Actualiza (status + applied_at / is_favorite / notes)
    V-->>B: {ok} — sin recargar la página
```

### 9. Ver perfil

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant V as Vista profile
    participant DB as PostgreSQL
    U->>B: Abre /perfil/
    B->>V: GET /perfil/ (login_required)
    V->>DB: Owner + CV activo + métricas (ofertas/postuladas/favoritas)
    V-->>B: Página de perfil
```

---

## Estructura del proyecto

```
find-job-please/
├── docker-compose.yml          db (Postgres) + web (Django)
├── com.andres.findjob.plist    sync programado (launchd)
└── web/
    ├── config/                 settings · urls · wsgi
    └── jobs/
        ├── models.py           User↔Owner · CV · Job
        ├── views.py            auth, lista, detalle, sync, cv, acciones, perfil
        ├── forms.py            registro
        ├── sync.py             orquesta fuentes → dedup → rank (hilo background)
        ├── services/
        │   ├── config.py       filtros (48h, 15/plataforma, tope 30)
        │   ├── scraper.py      JobSpy (LinkedIn/Indeed)
        │   ├── importer.py     DataFrame → upsert
        │   ├── dedup.py        duplicados lógicos
        │   ├── cv.py           PDF → texto + keywords
        │   ├── rankers/        keyword · embeddings (E5)
        │   └── connectors/     getonbrd · jobicy · torre · remotive
        └── templates/          job_list · job_detail · profile · registration/*
```
