"""Ranker léxico: cuenta keywords del CV en la oferta y lo escala a 0–100."""
from .base import BaseRanker

# Nº de keywords que equivale a un match de 100.
_CAP = 8


class KeywordRanker(BaseRanker):
    name = "keyword"

    def rank(self, owner) -> int:
        from ...models import Job
        from .. import cv as cv_service, scraper

        kw = cv_service.active_keywords(owner)
        jobs = list(Job.objects.filter(owner=owner))
        for j in jobs:
            count = scraper.score_text(j.title, j.description, j.company, kw)
            j.match_score = round(100 * min(count / _CAP, 1.0))
        Job.objects.bulk_update(jobs, ["match_score"], batch_size=500)
        return len(jobs)
