"""
Sincroniza ofertas desde todas las fuentes hacia la BD, por dueño.

Uso:
    docker compose exec web python manage.py sync_jobs                 # todos los dueños
    docker compose exec web python manage.py sync_jobs --email a@b.com  # uno solo
"""
from django.core.management.base import BaseCommand

from jobs.models import Job, Owner
from jobs.sync import run_sync


class Command(BaseCommand):
    help = "Busca ofertas y las guarda en la BD para cada dueño (por su CV)"

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Sincronizar solo este correo")

    def handle(self, *args, **opts):
        owners = Owner.objects.all()
        if opts.get("email"):
            owners = owners.filter(email=opts["email"])
        if not owners.exists():
            self.stdout.write(self.style.WARNING(
                "No hay dueños registrados. Sube un CV primero."
            ))
            return

        for owner in owners:
            self.stdout.write(f"→ Sincronizando {owner.email} (puede tardar ~1–2 min)…")
            result = run_sync(owner)
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ {result['created']} nuevas, {result['updated']} actualizadas "
                f"({Job.objects.filter(owner=owner).count()} en total para {owner.email})"
            ))
