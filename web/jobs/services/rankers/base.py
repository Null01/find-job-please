"""Interfaz común de los rankers. Cada estrategia implementa rank(owner)."""


class BaseRanker:
    name = "base"

    def rank(self, owner) -> int:
        """Recalcula match_score (0–100) de todas las ofertas del dueño.

        Devuelve cuántas ofertas se re-puntuaron.
        """
        raise NotImplementedError
