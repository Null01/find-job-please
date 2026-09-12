"""
Servicios de dominio de la app `jobs`.

- config:   filtros de búsqueda "quemados".
- scraper:  obtiene ofertas desde JobSpy y las rankea.
- importer: hace upsert de un DataFrame de ofertas a la base de datos.

Toda la lógica reutilizable vive aquí, para que la use el botón de la web
(`jobs.sync`), el comando `manage.py sync_jobs` o cualquier tarea futura.
"""
