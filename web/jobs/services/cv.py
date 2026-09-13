"""
Servicio de CV: extrae texto de un PDF, deriva palabras clave técnicas y las
integra al scoring del match.

La extracción es por vocabulario (determinista, sin llamadas externas): busca
tecnologías conocidas dentro del texto del CV. Más adelante se puede mejorar con
un LLM para inferencia semántica.
"""
import re

from . import config as cfg

# Vocabulario de habilidades tech (relevante para LatAm). Se puede ampliar.
SKILL_VOCAB = [
    # Lenguajes
    "python", "javascript", "typescript", "java", "kotlin", "swift", "golang",
    "go", "rust", "ruby", "php", "c#", "c++", "scala", "elixir", "dart",
    # Frontend
    "react", "angular", "vue", "svelte", "next.js", "nuxt", "redux", "tailwind",
    "html", "css", "sass",
    # Backend / APIs
    "node", "node.js", "express", "nestjs", "django", "flask", "fastapi",
    "spring", "spring boot", "rails", "laravel", ".net", "asp.net", "graphql",
    "rest", "rest api", "grpc", "microservices", "serverless",
    # Mobile
    "react native", "flutter", "android", "ios",
    # Datos
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "spark", "hadoop", "snowflake", "dbt", "airflow", "pandas", "numpy",
    # ML / AI
    "machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "llm",
    "scikit-learn", "opencv",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "ci/cd", "gitlab", "github actions", "linux", "nginx", "lambda",
    # Prácticas
    "agile", "scrum", "tdd",
]


def extract_text(source) -> str:
    """Extrae el texto de un PDF con pypdf.

    `source` puede ser una ruta local (str) o un objeto tipo archivo (stream).
    Aceptar un stream permite leer desde object storage (R2/S3), donde no hay
    ruta local en disco.
    """
    from pypdf import PdfReader

    reader = PdfReader(source)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_keywords(text: str, vocab=None, limit: int = 30) -> list[str]:
    """Devuelve las tecnologías del vocabulario que aparecen en el texto."""
    vocab = vocab or SKILL_VOCAB
    low = text.lower()
    found = []
    for term in vocab:
        tl = term.lower()
        # Palabra simple (solo letras/números): usa límites de palabra.
        if re.fullmatch(r"[a-z0-9]+", tl):
            hit = re.search(rf"\b{re.escape(tl)}\b", low) is not None
        else:
            hit = tl in low  # términos con símbolos o varias palabras: subcadena
        if hit and term not in found:
            found.append(term)
    return found[:limit]


def active_keywords(owner=None) -> list[str]:
    """Keywords base (config) + las del CV activo del dueño, sin duplicados."""
    from ..models import CV

    merged = list(cfg.KEYWORDS_BOOST)
    seen = {k.lower() for k in merged}

    cv = None
    if owner is not None:
        cv = (
            CV.objects.filter(owner=owner, is_active=True)
            .exclude(keywords=[])
            .order_by("-analyzed_at")
            .first()
        )
    for kw in (cv.keywords if cv else []):
        if kw.lower() not in seen:
            merged.append(kw)
            seen.add(kw.lower())
    return merged
