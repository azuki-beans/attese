from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import redirect
from django.templatetags.static import static as static_url
from django.urls import include, path

from attese.sitemaps import sitemaps
from attese.views import robots_txt


def _admin_login(request, **kwargs):
    """Reindirizza al login Google invece di mostrare il form Django admin."""
    return redirect(f"/accounts/google/login/?next={request.get_full_path()}")

admin.site.login = _admin_login


def _favicon(request):
    """Browser e crawler chiedono /favicon.ico a prescindere dai <link>."""
    return redirect(static_url("images/favicon-32.png"), permanent=True)


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("favicon.ico", _favicon),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
]

urlpatterns += i18n_patterns(path("", include("attese.urls")), prefix_default_language=False)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
