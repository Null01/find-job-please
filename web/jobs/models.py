import re

from django.conf import settings
from django.db import models


def cv_upload_path(instance, filename):
    """Guarda cada CV en una carpeta nombrada con el correo: cv/<email>/<archivo>."""
    folder = re.sub(r"[^A-Za-z0-9._@+-]", "_", instance.email or "unknown")
    return f"cv/{folder}/{filename}"


class Owner(models.Model):
    """Dueño de un CV y de sus ofertas, vinculado a un usuario con login."""

    class Gender(models.TextChoices):
        MALE = "M", "Masculino"
        FEMALE = "F", "Femenino"
        OTHER = "O", "Otro"
        NA = "N", "Prefiero no decir"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="owner", null=True, blank=True,
    )
    email = models.EmailField("Correo", unique=True)
    full_name = models.CharField("Nombres", max_length=200, blank=True)
    birth_date = models.DateField("Fecha de nacimiento", null=True, blank=True)
    gender = models.CharField("Género", max_length=1, choices=Gender.choices, blank=True)
    created_at = models.DateTimeField("Registrado", auto_now_add=True)

    class Meta:
        ordering = ["email"]
        verbose_name = "Dueño"
        verbose_name_plural = "Dueños"

    def __str__(self) -> str:
        return self.email


class CV(models.Model):
    """CV en PDF subido por el usuario, asociado a un correo."""

    owner = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="cvs", null=True, blank=True
    )
    email = models.EmailField("Correo")
    file = models.FileField("Archivo", upload_to=cv_upload_path)
    uploaded_at = models.DateTimeField("Subido", auto_now_add=True)
    text = models.TextField("Texto extraído", blank=True)
    keywords = models.JSONField("Palabras clave", default=list, blank=True)
    analyzed_at = models.DateTimeField("Analizado", null=True, blank=True)
    is_active = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "CV"
        verbose_name_plural = "CVs"

    def __str__(self) -> str:
        return f"{self.email} ({self.uploaded_at:%Y-%m-%d})"

    @property
    def filename(self) -> str:
        return self.file.name.rsplit("/", 1)[-1] if self.file else ""


class Job(models.Model):
    """Una oferta de empleo agregada desde alguna bolsa (LinkedIn, Indeed, ...)."""

    class Status(models.TextChoices):
        NEW = "new", "Sin postular"
        APPLIED = "applied", "Postulada"
        INTERVIEW = "interview", "Entrevista"
        OFFER = "offer", "Oferta"
        REJECTED = "rejected", "Rechazada"
        DISCARDED = "discarded", "Descartada"

    # Dueño (quién subió el CV al que pertenecen estas ofertas)
    owner = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="jobs", null=True, blank=True
    )

    # Identidad / origen
    job_url = models.URLField("URL", max_length=1000)
    job_url_direct = models.URLField("URL directa", max_length=1000, blank=True)
    site = models.CharField("Bolsa", max_length=50, blank=True)
    search_term = models.CharField("Búsqueda", max_length=200, blank=True)

    # Datos de la oferta
    title = models.CharField("Título", max_length=500)
    company = models.CharField("Empresa", max_length=300, blank=True)
    location = models.CharField("Ubicación", max_length=300, blank=True)
    is_remote = models.BooleanField("Remoto", null=True, blank=True)
    job_type = models.CharField("Tipo", max_length=100, blank=True)
    date_posted = models.DateField("Publicada", null=True, blank=True)

    # Salario (cuando la bolsa lo expone)
    min_amount = models.FloatField("Salario mín.", null=True, blank=True)
    max_amount = models.FloatField("Salario máx.", null=True, blank=True)
    currency = models.CharField("Moneda", max_length=10, blank=True)

    description = models.TextField("Descripción", blank=True)

    # Contexto de empresa (enriquecimiento desde JobSpy)
    company_url = models.URLField("Web empresa", max_length=1000, blank=True)
    company_logo = models.URLField("Logo", max_length=1000, blank=True)
    company_industry = models.CharField("Industria", max_length=200, blank=True)
    company_num_employees = models.CharField("Tamaño", max_length=100, blank=True)

    # Seguimiento de la postulación
    status = models.CharField("Estado", max_length=20, choices=Status.choices,
                              default=Status.NEW, db_index=True)
    applied_at = models.DateTimeField("Fecha de postulación", null=True, blank=True)
    is_favorite = models.BooleanField("Favorita", default=False)
    notes = models.TextField("Notas", blank=True)

    # Ranking / metadatos
    match_score = models.IntegerField("Match", default=0, db_index=True)
    embedding = models.JSONField("Vector", null=True, blank=True, default=None)
    embedding_model = models.CharField("Modelo del vector", max_length=120, blank=True)
    created_at = models.DateTimeField("Guardada", auto_now_add=True)

    class Meta:
        ordering = ["-match_score", "-date_posted", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "job_url"], name="uniq_owner_job_url"
            ),
        ]
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["site"]),
            models.Index(fields=["company"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} · {self.company}"

    @property
    def salary_display(self) -> str:
        if self.min_amount and self.max_amount:
            return f"{self.currency} {self.min_amount:,.0f}–{self.max_amount:,.0f}"
        if self.min_amount:
            return f"{self.currency} {self.min_amount:,.0f}+"
        return "—"

    @property
    def has_salary(self) -> bool:
        return bool(self.min_amount or self.max_amount)

    @property
    def posted_ago(self) -> str:
        """Fecha relativa en español: 'hoy', 'ayer', 'hace N días/semanas/meses'."""
        if not self.date_posted:
            return ""
        from django.utils import timezone
        days = (timezone.localdate() - self.date_posted).days
        if days <= 0:
            return "hoy"
        if days == 1:
            return "ayer"
        if days < 14:
            return f"hace {days} días"
        if days < 60:
            return f"hace {days // 7} semanas"
        return f"hace {days // 30} meses"
