import json

from django.conf import settings
from django.db.models import Avg, Max
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views import View

from .models import DataFetchLog, WaitingRecord


def latest_records(activity_code):
    """
    Record dell'ultima pubblicazione opendata per una prestazione.
    Le pubblicazioni precedenti restano nel DB solo per lo storico dei grafici.
    """
    qs = WaitingRecord.objects.filter(activity_code=activity_code)
    latest = qs.aggregate(Max("publish_date"))["publish_date__max"]
    return qs.filter(publish_date=latest).select_related("structure").order_by("waiting_days")


def current_activities():
    """Prestazioni presenti nell'ultima pubblicazione opendata, in ordine alfabetico."""
    latest = WaitingRecord.objects.aggregate(Max("publish_date"))["publish_date__max"]
    return (
        WaitingRecord.objects
        .filter(publish_date=latest)
        .values("activity_code", "activity_description_it")
        .distinct()
        .order_by("activity_description_it")
    )


class DashboardView(View):
    """
    Pagina principale pubblica con i due filtri (prestazione e struttura).
    Mostra solo il select delle prestazioni al caricamento.
    La struttura e i risultati vengono caricati via HTMX quando si seleziona una prestazione.
    """

    def get(self, request):
        activities = (
            WaitingRecord.objects
            .values("activity_code", "activity_description_it")
            .distinct()
            .order_by("activity_description_it")
        )
        has_data = WaitingRecord.objects.exists()
        last_fetch = DataFetchLog.objects.first()
        return render(request, "attese/dashboard.html", {
            "activities": activities,
            "current_activities": current_activities(),
            "has_data": has_data,
            "last_fetch": last_fetch,
        })


class ActivityIndexView(View):
    """Elenco A–Z delle prestazioni, con un link alla pagina di ciascuna (indicizzabile)."""

    def get(self, request):
        return render(request, "attese/activity_index.html", {
            "current_activities": current_activities(),
        })


class ActivityDetailView(View):
    """
    Pagina pubblica di una prestazione, renderizzata lato server (niente htmx):
    è quella che Google indicizza per ricerche tipo "tempi di attesa visita oculistica Bolzano".
    """

    def get(self, request, code, slug=None):
        records = list(latest_records(code))
        if not records:
            raise Http404("Prestazione non trovata")

        activity = records[0]
        canonical_slug = slugify(activity.activity_description_it)
        if slug != canonical_slug:
            return redirect("activity_detail", code=code, slug=canonical_slug, permanent=True)

        best = next((r for r in records if r.waiting_days is not None), None)
        return render(request, "attese/activity_detail.html", {
            "activity": activity,
            "records": records,
            "best": best,
        })


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /django-admin/",
        "Disallow: /accounts/",
        "Disallow: /partials/",
        "Disallow: /i18n/",
        "",
        f"Sitemap: {settings.SITE_URL.rstrip('/')}{reverse('sitemap')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


class FilterPartialView(View):
    """
    HTMX endpoint: al cambio della prestazione aggiorna il select delle strutture
    e mostra i risultati per quella prestazione (tutte le strutture).
    """

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()

        if not activity_code:
            return render(request, "attese/partials/empty.html")

        structures = (
            WaitingRecord.objects
            .filter(activity_code=activity_code)
            .values("structure__description_it")
            .distinct()
            .order_by("structure__description_it")
        )

        records = latest_records(activity_code)

        return render(request, "attese/partials/filter_area.html", {
            "activity_code": activity_code,
            "structures": structures,
            "records": records,
        })


class ResultsPartialView(View):
    """
    HTMX endpoint: al cambio della struttura aggiorna solo la tabella dei risultati.
    """

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()
        structure = request.GET.get("structure", "").strip()

        if not activity_code:
            return render(request, "attese/partials/empty.html")

        records = latest_records(activity_code)
        if structure:
            records = records.filter(structure=structure)

        return render(request, "attese/partials/results_table.html", {
            "records": records,
            "activity_code": activity_code,
            "structure": structure,
        })


def _qs_to_chart_data(qs):
    """Converte un queryset {publish_date, avg} in labels/data per Chart.js."""
    rows = list(qs)
    labels = [str(r["publish_date"]) for r in rows if r["publish_date"]]
    data = [round(r["avg"], 1) if r["avg"] is not None else None for r in rows]
    return labels, data


class StatisticsView(View):
    def get(self, request):
        activities = (
            WaitingRecord.objects
            .values("activity_code", "activity_description_it")
            .distinct()
            .order_by("activity_description_it")
        )

        global_qs = (
            WaitingRecord.objects
            .filter(waiting_days__isnull=False)
            .values("publish_date")
            .annotate(avg=Avg("waiting_days"))
            .order_by("publish_date")
        )
        global_labels, global_data = _qs_to_chart_data(global_qs)

        return render(request, "attese/statistics.html", {
            "activities": activities,
            "global_labels": json.dumps(global_labels),
            "global_data": json.dumps(global_data),
        })


class ActivityChartPartialView(View):
    """HTMX: grafico media tempi per una prestazione nel tempo."""

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()
        if not activity_code:
            return render(request, "attese/partials/chart_empty.html")

        qs = (
            WaitingRecord.objects
            .filter(activity_code=activity_code, waiting_days__isnull=False)
            .values("publish_date")
            .annotate(avg=Avg("waiting_days"))
            .order_by("publish_date")
        )
        labels, data = _qs_to_chart_data(qs)

        activity_label = (
            WaitingRecord.objects
            .filter(activity_code=activity_code)
            .values_list("activity_description_it", flat=True)
            .first() or activity_code
        )

        return render(request, "attese/partials/activity_chart.html", {
            "activity_label": activity_label,
            "labels": json.dumps(labels),
            "data": json.dumps(data),
        })


class StructurePickerPartialView(View):
    """HTMX: carica il select delle strutture per una prestazione (pannello 3)."""

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()
        if not activity_code:
            return render(request, "attese/partials/chart_empty.html")

        structures = (
            WaitingRecord.objects
            .filter(activity_code=activity_code)
            .values("structure__id", "structure__description_it")
            .distinct()
            .order_by("structure__description_it")
        )
        return render(request, "attese/partials/structure_picker.html", {
            "activity_code": activity_code,
            "structures": structures,
        })


class StructureChartPartialView(View):
    """HTMX: grafico tempo di attesa di una prestazione in una struttura nel tempo."""

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()
        structure_id = request.GET.get("structure_id", "").strip()

        if not activity_code or not structure_id:
            return render(request, "attese/partials/chart_empty.html")

        qs = (
            WaitingRecord.objects
            .filter(activity_code=activity_code, structure_id=structure_id, waiting_days__isnull=False)
            .values("publish_date")
            .annotate(avg=Avg("waiting_days"))
            .order_by("publish_date")
        )
        labels, data = _qs_to_chart_data(qs)

        structure_label = (
            WaitingRecord.objects
            .filter(structure_id=structure_id)
            .values_list("structure__description_it", flat=True)
            .first() or ""
        )
        activity_label = (
            WaitingRecord.objects
            .filter(activity_code=activity_code)
            .values_list("activity_description_it", flat=True)
            .first() or activity_code
        )

        return render(request, "attese/partials/structure_chart.html", {
            "labels": json.dumps(labels),
            "data": json.dumps(data),
            "activity_label": activity_label,
            "structure_label": structure_label,
        })
