from django.conf import settings
from django.urls import translate_url

from .lingue import codici_lingua


def site(request):
    """SITE_URL nei template: base per canonical e Open Graph (sempre il dominio pubblico)."""
    return {"SITE_URL": settings.SITE_URL.rstrip("/")}


def lingue(request):
    """
    La stessa pagina in ogni lingua (hreflang e pulsante IT/DE). La pagina di una prestazione
    passa le proprie `lingue_alternative`: lì cambia anche lo slug.
    """
    return {"lingue_alternative": {codice: translate_url(request.path, codice) for codice in codici_lingua()}}
