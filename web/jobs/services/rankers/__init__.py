"""
Rankers del match, conectables por configuración.

`RANKER_STRATEGY` (env) elige la estrategia activa: "embeddings" (local,
semántico; por defecto) o "keyword" (léxico simple). Cambiarla y reiniciar el
web conecta/desconecta la estrategia sin tocar código.

Agregar una estrategia nueva (p. ej. "llm") = un archivo aquí + una entrada en
el registro de abajo.
"""
import os


def get_active_ranker():
    strategy = os.environ.get("RANKER_STRATEGY", "embeddings").lower()
    if strategy == "keyword":
        from .keyword import KeywordRanker
        return KeywordRanker()
    # "embeddings" y cualquier valor desconocido → semántico local (default).
    from .embeddings import EmbeddingsRanker
    return EmbeddingsRanker()
