#!/usr/bin/env bash
#
# rotate-local-secrets.sh — Rota los secretos LOCALES del archivo .env.
#
# Rota DJANGO_SECRET_KEY y POSTGRES_PASSWORD con valores nuevos y aleatorios:
#   - Si NO existe .env, lo crea desde .env.example.
#   - Si YA existe, rota SOLO esas dos claves y respalda el anterior en
#     .env.<timestamp>.bak (conserva el resto de tu configuración).
#
# Los valores nuevos NO se imprimen: se escriben directo al .env.
#
# Uso:
#   ./deploy/rotate-local-secrets.sh
#
# Nota: tras rotar POSTGRES_PASSWORD, si ya tenías un volumen de Postgres
# inicializado, recréalo para que tome la nueva contraseña:
#   docker compose down -v && docker compose up -d
#
set -euo pipefail

# Raíz del repo = carpeta padre de este script (deploy/..), sin importar el cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

command -v python3 >/dev/null 2>&1 || { echo "❌ Se requiere python3." >&2; exit 1; }

python3 - <<'PY'
import secrets, string, pathlib, datetime, sys

env_path = pathlib.Path(".env")
tpl_path = pathlib.Path(".env.example")

# Alfabeto sin caracteres que compliquen shells/sed (?, $, &, /, \, |, comillas).
alpha  = string.ascii_letters + string.digits + "!@#%^*-_=+"
secret = "".join(secrets.choice(alpha) for _ in range(50))
dbpass = secrets.token_urlsafe(24)

if env_path.exists():
    src = env_path.read_text()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = pathlib.Path(f".env.{stamp}.bak")
    backup.write_text(src)
    origin = f"rotado (respaldo: {backup.name})"
elif tpl_path.exists():
    src = tpl_path.read_text()
    origin = "creado desde .env.example"
else:
    sys.exit("❌ No hay .env ni .env.example en la raíz del repo.")

def set_key(text, key, value):
    lines, found = text.splitlines(), False
    for i, line in enumerate(lines):
        if line.startswith(key + "="):   # ignora líneas comentadas (#KEY=...)
            lines[i], found = f"{key}={value}", True
    if not found:
        lines.append(f"{key}={value}")
    return "\n".join(lines)

out = set_key(src, "DJANGO_SECRET_KEY", secret)
out = set_key(out, "POSTGRES_PASSWORD", dbpass)
env_path.write_text(out.rstrip("\n") + "\n")

print(f"✅ .env {origin}.")
print("✅ DJANGO_SECRET_KEY y POSTGRES_PASSWORD rotados (valores no mostrados).")
PY

# Confirma que .env no se subirá al repo.
if git check-ignore .env >/dev/null 2>&1; then
    echo "✅ .env está en .gitignore (no se subirá)."
else
    echo "⚠️  .env NO está ignorado por git. Revísalo antes de commitear."
fi
