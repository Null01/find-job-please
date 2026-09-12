from django.shortcuts import redirect

# Prefijos que NO deben redirigir (admin, archivos): dejan su propio 404.
_SKIP_PREFIXES = ("/admin/", "/static/", "/media/")


class NotFoundRedirectMiddleware:
    """Cualquier ruta inexistente (404) redirige:

    - con sesión iniciada → a las ofertas (home)
    - sin sesión → al login
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404 and not request.path.startswith(_SKIP_PREFIXES):
            if request.user.is_authenticated:
                return redirect("jobs:list")
            return redirect("login")
        return response
