"""
Conectores a plataformas de empleo distintas de JobSpy.

Cada conector expone `fetch(...) -> pandas.DataFrame` con el esquema común que
espera `jobs.services.importer.upsert_jobs` (columna obligatoria: job_url).
Así agregar una plataforma nueva = un archivo aquí.
"""
