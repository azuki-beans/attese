from django.conf import settings


def site(request):
    """SITE_URL nei template: base per canonical e Open Graph (sempre il dominio pubblico)."""
    return {"SITE_URL": settings.SITE_URL.rstrip("/")}
