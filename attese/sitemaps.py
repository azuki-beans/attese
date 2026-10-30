from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse
from django.utils.text import slugify

from .models import WaitingRecord


class SiteUrlSitemap(Sitemap):
    """
    Dominio e schema presi da SITE_URL, non dal modello Site (che serve solo ad allauth):
    così la sitemap punta sempre al dominio pubblico, anche se la richiesta arriva da *.run.app.
    """

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


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
            .values("activity_code", "activity_description_it", "publish_date")
            .distinct()
            .order_by("activity_code")
        )

    def location(self, item):
        return reverse("activity_detail", kwargs={
            "code": item["activity_code"],
            "slug": slugify(item["activity_description_it"]),
        })

    def lastmod(self, item):
        return item["publish_date"]


sitemaps = {"static": StaticSitemap, "prestazioni": ActivitySitemap}
