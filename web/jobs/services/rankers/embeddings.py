"""
Ranker semántico con embeddings locales (offline, sin API key).

Algoritmo (buenas prácticas de matching semántico):
1. Bi-encoder multilingüe E5 (query/passage) → embeddings normalizados.
2. Similitud coseno CV↔oferta.
3. Puntaje HÍBRIDO: 80% semántico (denso) + 20% léxico (keywords), como en los
   sistemas de retrieval densos+sparse.
4. Normalización min-max dentro del lote → 0–100 bien repartido.
5. Caché del vector por oferta (se re-encoda solo lo nuevo o si cambia el modelo).

Si sentence-transformers/torch no están disponibles o el modelo falla al cargar,
cae con gracia al ranker léxico para no romper la app.
"""
import os

from .base import BaseRanker

# Modelo cargado una sola vez por proceso.
_model = None
_model_name = None


def _get_model(name):
    global _model, _model_name
    if _model is not None and _model_name == name:
        return _model
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(name)
    _model_name = name
    return _model


class EmbeddingsRanker(BaseRanker):
    name = "embeddings"

    def __init__(self):
        self.model_name = os.environ.get(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
        )
        self.sem_w = float(os.environ.get("RANK_SEM_WEIGHT", "0.8"))
        self.lex_w = float(os.environ.get("RANK_LEX_WEIGHT", "0.2"))

    def rank(self, owner) -> int:
        import numpy as np
        from ...models import CV, Job
        from .. import cv as cv_service, scraper

        try:
            model = _get_model(self.model_name)
        except Exception:  # noqa: BLE001 - sin modelo/torch → léxico
            from .keyword import KeywordRanker
            return KeywordRanker().rank(owner)

        jobs = list(Job.objects.filter(owner=owner))
        if not jobs:
            return 0

        kw = cv_service.active_keywords(owner)
        cv = (
            CV.objects.filter(owner=owner, is_active=True)
            .order_by("-analyzed_at", "-uploaded_at")
            .first()
        )
        cv_text = (cv.text if cv and cv.text else "").strip()

        # Consulta = keywords (peso al stack) + resumen del CV, con prefijo E5.
        query = "query: " + " ".join(kw) + " " + cv_text[:2000]
        q_emb = model.encode([query], normalize_embeddings=True)[0]

        # Embeddings de ofertas, reusando caché válida.
        embs = [None] * len(jobs)
        to_encode, idx = [], []
        for i, j in enumerate(jobs):
            if j.embedding and j.embedding_model == self.model_name:
                embs[i] = np.asarray(j.embedding, dtype="float32")
            else:
                passage = "passage: %s. %s. %s. %s" % (
                    j.title, j.company, j.location, (j.description or "")[:2000]
                )
                to_encode.append(passage)
                idx.append(i)

        if to_encode:
            new = model.encode(to_encode, normalize_embeddings=True, batch_size=16)
            for k, i in enumerate(idx):
                vec = np.asarray(new[k], dtype="float32")
                embs[i] = vec
                jobs[i].embedding = [float(x) for x in vec]
                jobs[i].embedding_model = self.model_name

        # Similitud coseno (vectores ya normalizados → producto punto).
        sims = np.array([float(np.dot(q_emb, e)) for e in embs], dtype="float32")
        smin, smax = float(sims.min()), float(sims.max())
        sem = (sims - smin) / (smax - smin) if smax > smin else np.full_like(sims, 0.5)

        # Señal léxica normalizada.
        lex_raw = np.array(
            [scraper.score_text(j.title, j.description, j.company, kw) for j in jobs],
            dtype="float32",
        )
        lmax = float(lex_raw.max())
        lex = lex_raw / lmax if lmax > 0 else np.zeros_like(lex_raw)

        final = (self.sem_w * sem + self.lex_w * lex) * 100.0
        for i, j in enumerate(jobs):
            j.match_score = int(round(float(final[i])))

        Job.objects.bulk_update(
            jobs, ["match_score", "embedding", "embedding_model"], batch_size=200
        )
        return len(jobs)
