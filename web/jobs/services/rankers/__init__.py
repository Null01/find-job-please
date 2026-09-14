"""
Rankers del match, conectables por configuración.

`BUSINESS_RANKER_STRATEGY` (env) elige la estrategia activa: "embeddings" (local,
semántico; por defecto) o "keyword" (léxico simple). Cambiarla y reiniciar el
web conecta/desconecta la estrategia sin tocar código.

Agregar una estrategia nueva (p. ej. "llm") = un archivo aquí + una entrada en
el registro de abajo.
"""
import os


def get_active_ranker():
    strategy = os.environ.get("BUSINESS_RANKER_STRATEGY", "embeddings").lower()
    if strategy != "keyword":
        # "embeddings" (o valor desconocido) → semántico, SOLO si sus dependencias
        # están instaladas. En la imagen slim (sin torch/sentence-transformers) cae
        # a keyword en vez de fallar.
        import importlib.util
        if importlib.util.find_spec("sentence_transformers") is not None:
            from .embeddings import EmbeddingsRanker
            return EmbeddingsRanker()
    from .keyword import KeywordRanker
    return KeywordRanker()
