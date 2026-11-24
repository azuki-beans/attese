from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from .lingue import slug, tedesco
from .models import WaitingRecord


class SiteUrlSitemap(Sitemap):
    """
    Dominio e schema presi da SITE_URL, non dal modello Site (che serve solo ad allauth):
    così la sitemap punta sempre al dominio pubblico, anche se la richiesta arriva da *.run.app.
    Ogni pagina c'è in tutte le lingue, con i rimandi hreflang.
    """

    i18n = True
    alternates = True
    x_default = True

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


def _slug_prestazione(item):
    nome_de = item["activity_description_de"].strip() if tedesco() else ""
    return slug(nome_de or item["activity_description_it"])


class StaticSitemap(SiteUrlSitemap):
    changefreq = "daily"

    def items(self):
        return ["dashboard", "activity_index", "statistics"]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return WaitingRecord.objects.aggregate(Max("publish_date"))["publish_date__max"]


class ActivitySitemap(SiteUrlSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        latest = WaitingRecord.objects.aggregate(Max("publish_date"))["publish_date__max"]
        return (
            WaitingRecord.objects
            .filter(publish_date=latest)
            .values("activity_code", "activity_description_it", "activity_description_de", "publish_date")
            .distinct()
            .order_by("activity_code")
        )

    def location(self, item):
        return reverse("activity_detail", kwargs={
            "code": item["activity_code"],
            "slug": _slug_prestazione(item),
        })

    def lastmod(self, item):
        return item["publish_date"]


sitemaps = {"static": StaticSitemap, "prestazioni": ActivitySitemap}
