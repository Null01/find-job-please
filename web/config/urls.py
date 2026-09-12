from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from jobs import views as jobs_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Autenticación
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", jobs_views.register, name="register"),
    path("password/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change.html",
        success_url="/perfil/",
    ), name="password_change"),
    path("", include("jobs.urls")),
]
