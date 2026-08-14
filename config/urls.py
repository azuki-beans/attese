from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def _admin_login(request, **kwargs):
    """Reindirizza al login Google invece di mostrare il form Django admin."""
    return redirect(f"/accounts/google/login/?next={request.get_full_path()}")

admin.site.login = _admin_login


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("attese.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
