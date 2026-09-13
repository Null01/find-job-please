"""Configuración de Django para el proyecto find-job-AI."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

_INSECURE_KEY = "dev-insecure-key-change-me-in-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_KEY)
if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY no está definido en producción (DEBUG=0). "
        "Genera uno e inyéctalo por entorno (ver DEPLOY.md)."
    )

# En prod exige dominios explícitos (nunca "*"); en local, "*" por comodidad.
ALLOWED_HOSTS = [
    h.strip() for h in
    os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jobs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve archivos estáticos (comprimidos) en producción, sin nginx.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Rutas inexistentes → home (con sesión) o login (sin sesión).
    "jobs.middleware.NotFoundRedirectMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de datos.
# Producción: BD remota (Supabase) vía DATABASE_URL, que inyecta el gestor de
# secretos (Infisical) o el entorno de la plataforma — nunca desde un archivo del repo.
# Desarrollo: si DATABASE_URL no está definida, cae al Postgres local (docker-compose),
# igual que hoy. Así el mismo código sirve para local y remoto.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "600")),
            # TLS obligatorio hacia una BD remota (Supabase lo exige).
            ssl_require=os.environ.get("DB_SSL_REQUIRE", "1") == "1",
        )
    }
    # El pooler de Supabase en modo "transaction" (puerto 6543) no soporta
    # cursores del lado servidor ni conexiones persistentes.
    if os.environ.get("DB_POOLER_MODE", "").lower() == "transaction":
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
        DATABASES["default"]["CONN_MAX_AGE"] = 0
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "findjob"),
            "USER": os.environ.get("POSTGRES_USER", "findjob"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "findjob"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # Rechaza contraseñas con score bajo de zxcvbn (exige al menos "media").
    {"NAME": "jobs.validators.ZxcvbnValidator", "OPTIONS": {"min_score": 2}},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"   # destino de collectstatic (lo sirve WhiteNoise)

# Autenticación
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "jobs:list"
LOGOUT_REDIRECT_URL = "login"

# Archivos subidos (CVs).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Almacenamiento.
#  - Media (CVs): Cloudflare R2 (S3-compatible) si R2_BUCKET está definido; si no,
#    disco local (desarrollo). R2 es object storage → persiste entre despliegues.
#  - Estáticos: WhiteNoise (comprimido + manifiesto) en prod; el default en local.
R2_BUCKET = os.environ.get("R2_BUCKET", "").strip()
if R2_BUCKET:
    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": R2_BUCKET,
            "access_key": os.environ.get("R2_ACCESS_KEY_ID", ""),
            "secret_key": os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            "endpoint_url": os.environ.get("R2_ENDPOINT_URL", ""),
            "region_name": os.environ.get("R2_REGION", "auto"),
            "signature_version": "s3v4",
            "addressing_style": "virtual",
            "file_overwrite": False,
            "default_acl": None,        # R2 no usa ACLs
            "querystring_auth": True,   # bucket privado → URLs firmadas
        },
    }
else:
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- Endurecimiento en producción (solo con DEBUG=0) ----------
if not DEBUG:
    # Render (y otros PaaS) terminan el TLS en su proxy: confía en X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Orígenes https de confianza para CSRF (coma-separados). Ej: https://app.onrender.com
    CSRF_TRUSTED_ORIGINS = [
        o.strip() for o in
        os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
        if o.strip()
    ]
