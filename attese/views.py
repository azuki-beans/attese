import json

from django.conf import settings
from django.db.models import Avg, Max, Min
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import override
from django.views import View

from .lingue import codici_lingua, localizzato, slug
from .models import DataFetchLog, Structure, WaitingRecord
from .sedi import sedi_attuali, trova_sede, ultima_pubblicazione


def latest_records(activity_code):
    """
    Record dell'ultima pubblicazione opendata per una prestazione.
    Le pubblicazioni precedenti restano nel DB solo per lo storico dei grafici.
    """
    qs = WaitingRecord.objects.filter(activity_code=activity_code)
    latest = qs.aggregate(Max("publish_date"))["publish_date__max"]
    return qs.filter(publish_date=latest).select_related("structure").order_by("waiting_days")


def _elenco(qs):
    """
    Prestazioni distinte (codice, nome nella lingua attiva, slug, lettera), in ordine alfabetico.
    Si ordina in Python sullo slug: per il database "Ösophago…" verrebbe dopo la Z.
    """
    righe = qs.order_by().values("activity_code", nome=localizzato("activity_description")).distinct()
    elenco = [{**r, "nome": r["nome"].strip(), "slug": slug(r["nome"])} for r in righe]
    for r in elenco:
        r["lettera"] = r["slug"][:1].upper()
    return sorted(elenco, key=lambda r: r["slug"])


def all_activities():
    """Tutte le prestazioni mai pubblicate (menu di ricerca e statistiche)."""
    return _elenco(WaitingRecord.objects.all())


def current_activities():
    """Prestazioni presenti nell'ultima pubblicazione opendata."""
    latest = WaitingRecord.objects.aggregate(Max("publish_date"))["publish_date__max"]
    return _elenco(WaitingRecord.objects.filter(publish_date=latest))


def _nome_prestazione(code):
    record = WaitingRecord.objects.filter(activity_code=code).order_by("-publish_date").first()
    return record.activity_description if record else code


def _alternative(nome_url, argomenti):
    """La stessa pagina nelle altre lingue, quando cambia anche lo slug e non solo il prefisso."""
    alternative = {}
    for lingua in codici_lingua():
        with override(lingua):
            alternative[lingua] = reverse(nome_url, args=argomenti())
    return alternative


class DashboardView(View):
    """
    Pagina principale pubblica con i due filtri (prestazione e struttura).
    Mostra solo il select delle prestazioni al caricamento.
    La struttura e i risultati vengono caricati via HTMX quando si seleziona una prestazione.
    """

    def get(self, request):
        activities = all_activities()
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
        if slug != activity.activity_slug:
            return redirect("activity_detail", code=code, slug=activity.activity_slug, permanent=True)

        best = next((r for r in records if r.waiting_days is not None), None)
        return render(request, "attese/activity_detail.html", {
            "activity": activity,
            "records": records,
            "best": best,
            "lingue_alternative": _alternative("activity_detail", lambda: [code, activity.activity_slug]),
        })


class StructureIndexView(View):
    """Elenco delle sedi per città, con un link alla pagina di ciascuna."""

    def get(self, request):
        sedi = sorted(sedi_attuali(), key=lambda s: (slug(s.citta), s.slug))
        return render(request, "attese/structure_index.html", {"sedi": sedi})


class StructureDetailView(View):
    """
    Pagina pubblica di una sede con tutte le sue prestazioni, per ricerche tipo
    "tempi di attesa ospedale di Merano". Il minimo provinciale permette il confronto.
    """

    def get(self, request, nome):
        sede = trova_sede(nome)
        if sede is None:
            raise Http404("Struttura non trovata")
        if nome != sede.slug:
            return redirect("structure_detail", nome=sede.slug, permanent=True)

        minimi = dict(
            WaitingRecord.objects
            .filter(publish_date=sede.publish_date, waiting_days__isnull=False)
            .order_by()
            .values("activity_code")
            .annotate(minimo=Min("waiting_days"))
            .values_list("activity_code", "minimo")
        )
        righe = sorted(sede.records, key=lambda r: r.activity_slug)
        for r in righe:
            r.minimo_provinciale = minimi.get(r.activity_code)

        attese = sede.con_attesa
        return render(request, "attese/structure_detail.html", {
            "sede": sede,
            "records": righe,
            "attese": attese,
            "breve": attese[0] if attese else None,
            "lunga": attese[-1] if attese else None,
            "noindex": not sede.indicizzabile or sede.publish_date != ultima_pubblicazione(),
            "lingue_alternative": _alternative("structure_detail", lambda: [sede.slug]),
        })


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /django-admin/",
        "Disallow: /accounts/",
        "Disallow: /partials/",
        "Disallow: /de/partials/",
        "Disallow: /i18n/",
        "",
        f"Sitemap: {settings.SITE_URL.rstrip('/')}{reverse('sitemap')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


class FilterPartialView(View):
    """
    HTMX endpoint: al cambio della prestazione mostra i risultati (tutte le strutture).
    """

    def get(self, request):
        activity_code = request.GET.get("activity_code", "").strip()

        if not activity_code:
            return render(request, "attese/partials/empty.html")

        records = latest_records(activity_code)

        return render(request, "attese/partials/filter_area.html", {
            "activity_code": activity_code,
            "records": records,
        })


def _qs_to_chart_data(qs):
    """Converte un queryset {publish_date, avg} in labels/data per Chart.js."""
    rows = list(qs)
    labels = [str(r["publish_date"]) for r in rows if r["publish_date"]]
    data = [round(r["avg"], 1) if r["avg"] is not None else None for r in rows]
    return labels, data


class StatisticsView(View):
    def get(self, request):
        activities = all_activities()

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
            "global_labels": global_labels,
            "global_data": global_data,
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

        activity_label = _nome_prestazione(activity_code)

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
            Structure.objects
            .filter(waiting_records__activity_code=activity_code)
            .order_by(localizzato("description"))
            .distinct()
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

        structure = Structure.objects.filter(pk=structure_id).first()
        structure_label = structure.description if structure else ""
        activity_label = _nome_prestazione(activity_code)

        return render(request, "attese/partials/structure_chart.html", {
            "labels": json.dumps(labels),
            "data": json.dumps(data),
            "activity_label": activity_label,
            "structure_label": structure_label,
        })
