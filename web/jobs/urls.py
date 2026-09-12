from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list, name="list"),
    path("perfil/", views.profile, name="profile"),
    path("sync/", views.sync_start, name="sync"),
    path("sync/status/", views.sync_status, name="sync_status"),
    path("cv/upload/", views.upload_cv, name="upload_cv"),
    path("cv/<int:pk>/analyze/", views.analyze_cv, name="analyze_cv"),
    path("job/<int:pk>/", views.job_detail, name="detail"),
    path("job/<int:pk>/status/", views.set_status, name="set_status"),
    path("job/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("job/<int:pk>/notes/", views.save_notes, name="save_notes"),
]
