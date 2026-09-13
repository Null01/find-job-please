from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ExpressionWrapper, F, IntegerField, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from django.urls import reverse

from .forms import OwnerForm, RegisterForm
from .models import CV, Job, Owner
from . import sync as sync_engine


def _current_owner(request):
    """Dueño (Owner) del usuario autenticado, o None."""
    if not request.user.is_authenticated:
        return None
    return Owner.objects.filter(user=request.user).first()


def register(request):
    """Registro con correo + contraseña; crea/enlaza su Owner e inicia sesión."""
    if request.user.is_authenticated:
        return redirect("jobs:list")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Enlaza un Owner existente con ese correo, o crea uno nuevo.
        owner, _ = Owner.objects.get_or_create(email=user.email)
        owner.user = user
        owner.save(update_fields=["user"])
        login(request, user)
        return redirect("jobs:list")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    """Perfil del usuario: cuenta, CV activo, keywords, métricas y edición."""
    owner = _current_owner(request)

    if request.method == "POST" and owner:
        form = OwnerForm(request.POST, instance=owner)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('jobs:profile')}?ok=1")
    else:
        form = OwnerForm(instance=owner)

    jobs = Job.objects.filter(owner=owner) if owner else Job.objects.none()
    active_cv = (
        CV.objects.filter(owner=owner, is_active=True).order_by("-uploaded_at").first()
        if owner else None
    )
    context = {
        "owner": owner,
        "form": form,
        "genders": Owner.Gender.choices,
        "saved": request.GET.get("ok") == "1",
        "active_cv": active_cv,
        "cvs": CV.objects.filter(owner=owner).order_by("-uploaded_at") if owner else [],
        "total_jobs": jobs.count(),
        "applied": jobs.filter(status__in=[
            Job.Status.APPLIED, Job.Status.INTERVIEW, Job.Status.OFFER]).count(),
        "favorites": jobs.filter(is_favorite=True).count(),
    }
    return render(request, "jobs/profile.html", context)


@login_required
def job_list(request):
    """Vista principal: lista las ofertas del dueño activo, con búsqueda y filtros."""
    owner = _current_owner(request)
    qs = Job.objects.filter(owner=owner) if owner else Job.objects.none()

    q = request.GET.get("q", "").strip()
    site = request.GET.get("site", "").strip()
    remote = request.GET.get("remote", "").strip()
    status = request.GET.get("status", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(company__icontains=q)
            | Q(location__icontains=q)
            | Q(description__icontains=q)
        )
    if site:
        qs = qs.filter(site=site)
    if remote == "1":
        qs = qs.filter(is_remote=True)
    if status:
        qs = qs.filter(status=status)

    # Orden: por tramo de ranking (de 10 en 10) y, dentro del tramo, las más
    # nuevas primero. Así una oferta nueva con buen match sube por encima de una
    # vieja de match apenas mayor.
    qs = qs.annotate(
        score_bucket=ExpressionWrapper(
            F("match_score") / 10, output_field=IntegerField()
        )
    ).order_by(
        "-score_bucket",
        F("date_posted").desc(nulls_last=True),
        "-match_score",
        "-created_at",
    )

    # KPIs sobre el resultado filtrado (antes de paginar).
    remote_count = qs.filter(is_remote=True).count()
    company_count = qs.exclude(company="").values("company").distinct().count()
    applied_count = qs.filter(
        status__in=[Job.Status.APPLIED, Job.Status.INTERVIEW, Job.Status.OFFER]
    ).count()

    # Tamaño de página (registros por página).
    allowed_sizes = [25, 50, 100]
    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in allowed_sizes:
        per_page = 25

    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page"))
    # Ventana de páginas con elipsis (…) alrededor de la actual.
    page_range = paginator.get_elided_page_range(
        page.number, on_each_side=1, on_ends=1
    )

    # Querystring con los filtros actuales (sin 'page'), para los enlaces del paginador.
    params = {k: v for k, v in (
        ("q", q), ("site", site), ("remote", remote),
        ("status", status), ("per_page", per_page),
    ) if v}
    querystring = urlencode(params)

    # Igual pero incluyendo la página actual, para volver al mismo punto tras el detalle.
    list_params = dict(params)
    if page.number and page.number != 1:
        list_params["page"] = page.number
    list_query = urlencode(list_params)

    # Para poblar el <select> de bolsas (solo las del dueño activo).
    owner_jobs = Job.objects.filter(owner=owner) if owner else Job.objects.none()
    sites = (
        owner_jobs.exclude(site="")
        .values_list("site", flat=True)
        .distinct()
        .order_by("site")
    )

    context = {
        "page_obj": page,
        "page_range": page_range,
        "total": paginator.count,
        "per_page": per_page,
        "page_sizes": allowed_sizes,
        "querystring": querystring,
        "remote_count": remote_count,
        "company_count": company_count,
        "applied_count": applied_count,
        "sites": sites,
        "statuses": Job.Status.choices,
        "list_query": list_query,
        "q": q,
        "site": site,
        "remote": remote,
        "status": status,
        "sync": sync_engine.get_status(),
        "owner": owner,
        "owner_job_count": owner_jobs.count(),
        "has_cv": CV.objects.filter(owner=owner, is_active=True).exists() if owner else False,
    }
    return render(request, "jobs/job_list.html", context)


def _get_owned_job(request, pk):
    """Devuelve la oferta pk solo si pertenece al dueño activo, o None."""
    owner = _current_owner(request)
    if not owner:
        return None
    return Job.objects.filter(owner=owner, pk=pk).first()


@login_required
def job_detail(request, pk):
    """Vista de detalle de una oferta: descripción completa, notas, seguimiento."""
    job = _get_owned_job(request, pk)
    if not job:
        raise Http404("Oferta no encontrada")
    return render(request, "jobs/job_detail.html", {
        "job": job,
        "statuses": Job.Status.choices,
        # Filtros que venían en la URL, para reconstruir el enlace de vuelta.
        "back_query": request.GET.urlencode(),
    })


@login_required
@require_POST
def save_notes(request, pk):
    """Guarda las notas de una oferta."""
    job = _get_owned_job(request, pk)
    if not job:
        return JsonResponse({"ok": False}, status=404)
    job.notes = request.POST.get("notes", "")
    job.save(update_fields=["notes"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def sync_start(request):
    """Dispara la sincronización en segundo plano para el dueño activo."""
    owner = _current_owner(request)
    if not owner:
        return JsonResponse({
            "ok": False, "running": False,
            "message": "Sube tu CV primero para sincronizar.",
        }, status=400)
    started = sync_engine.start_background_sync(owner)
    status = sync_engine.get_status()
    status["started"] = started
    return JsonResponse(status)


@login_required
def sync_status(request):
    """Estado actual de la sincronización (para polling desde la web)."""
    return JsonResponse(sync_engine.get_status())


@login_required
@require_POST
def upload_cv(request):
    """Sube un CV en PDF para el usuario autenticado."""
    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"ok": False, "error": "Falta el archivo."}, status=400)
    if not file.name.lower().endswith(".pdf"):
        return JsonResponse({"ok": False, "error": "Solo se permiten archivos PDF."}, status=400)

    owner = _current_owner(request)
    if not owner:  # por si el usuario aún no tuviera Owner
        owner, _ = Owner.objects.get_or_create(email=request.user.email or request.user.username)
        owner.user = request.user
        owner.save(update_fields=["user"])

    job_count = Job.objects.filter(owner=owner).count()

    # El CV nuevo pasa a ser el activo del dueño.
    CV.objects.filter(owner=owner, is_active=True).update(is_active=False)
    cv = CV.objects.create(owner=owner, email=owner.email, file=file, is_active=True)

    return JsonResponse({
        "ok": True, "id": cv.id, "email": cv.email, "filename": cv.filename,
        "existing": job_count > 0,        # ya tiene ofertas guardadas
        "job_count": job_count,
    })


@login_required
@require_POST
def analyze_cv(request, pk):
    """Extrae palabras clave del CV y recalcula el match de las ofertas."""
    from django.utils import timezone
    from .services import cv as cv_service

    cv = get_object_or_404(CV, pk=pk, owner=_current_owner(request))
    try:
        # Lee como stream (funciona con disco local y con object storage R2/S3).
        with cv.file.open("rb") as fh:
            text = cv_service.extract_text(fh)
    except Exception as e:  # noqa: BLE001
        return JsonResponse({"ok": False, "error": f"No se pudo leer el PDF: {e}"}, status=400)

    keywords = cv_service.extract_keywords(text)
    cv.text = text
    cv.keywords = keywords
    cv.analyzed_at = timezone.now()
    cv.save(update_fields=["text", "keywords", "analyzed_at"])

    # Quita duplicados lógicos ANTES de rankear, luego aplica la estrategia activa.
    from .services import dedup
    from .services.rankers import get_active_ranker
    dedup.dedup_owner_jobs(cv.owner)
    rescored = get_active_ranker().rank(cv.owner)
    return JsonResponse({"ok": True, "keywords": keywords, "rescored": rescored})


@login_required
@require_POST
def set_status(request, pk):
    """Cambia el estado de postulación de una oferta."""
    from django.utils import timezone

    valid = {c for c, _ in Job.Status.choices}
    new_status = request.POST.get("status", "")
    if new_status not in valid:
        return JsonResponse({"ok": False, "error": "Estado inválido"}, status=400)

    job = _get_owned_job(request, pk)
    if not job:
        return JsonResponse({"ok": False, "error": "No existe"}, status=404)

    job.status = new_status
    # Marca la fecha la primera vez que pasa a "postulada".
    if new_status == Job.Status.APPLIED and job.applied_at is None:
        job.applied_at = timezone.now()
    job.save(update_fields=["status", "applied_at"])

    return JsonResponse({
        "ok": True,
        "status": job.status,
        "label": job.get_status_display(),
    })


@login_required
@require_POST
def toggle_favorite(request, pk):
    """Marca/desmarca una oferta como favorita."""
    job = _get_owned_job(request, pk)
    if not job:
        return JsonResponse({"ok": False}, status=404)
    job.is_favorite = not job.is_favorite
    job.save(update_fields=["is_favorite"])
    return JsonResponse({"ok": True, "is_favorite": job.is_favorite})
