"""
Sedi: una struttura sanitaria come la intende chi cerca ("Ospedale di Merano").
Nei dati ogni reparto è una `Structure` a sé, con lo stesso nome: qui si raggruppano.
"""

from collections import Counter

from django.db.models import Max

from .models import Structure, WaitingRecord

# Sotto questa soglia la pagina è quasi vuota: resta raggiungibile, ma noindex e fuori dalla sitemap
MIN_ATTESE = 3


def ultima_pubblicazione():
    return WaitingRecord.objects.aggregate(Max("publish_date"))["publish_date__max"]


class Sede:
    """Reparti con lo stesso nome e i loro record di un'unica pubblicazione. I testi seguono la lingua attiva."""

    def __init__(self, records):
        self.records = records
        self.strutture = [r.structure for r in records]
        # la più vecchia decide il nome, così lo slug è lo stesso qualunque sia l'ordine dei record
        self.principale = min(self.strutture, key=lambda s: s.pk)
        self.publish_date = records[0].publish_date

    @property
    def nome(self):
        return self.principale.description

    @property
    def slug(self):
        return self.principale.sede_slug

    @property
    def citta(self):
        return Counter(s.city for s in self.strutture).most_common(1)[0][0]

    @property
    def indirizzi(self):
        """Indirizzi distinti, dal più frequente (alcuni reparti sono in un'altra via o città)."""
        conteggio = Counter(s.street_it.strip() for s in self.strutture)
        per_via = {s.street_it.strip(): s for s in reversed(self.strutture)}
        return [per_via[via] for via, _ in conteggio.most_common()]

    @property
    def con_attesa(self):
        return sorted((r for r in self.records if r.waiting_days is not None), key=lambda r: r.waiting_days)

    @property
    def indicizzabile(self):
        return len(self.con_attesa) >= MIN_ATTESE


def sedi_attuali():
    """Sedi presenti nell'ultima pubblicazione, in ordine di nome."""
    gruppi = {}
    records = WaitingRecord.objects.filter(publish_date=ultima_pubblicazione()).select_related("structure")
    for r in records:
        gruppi.setdefault(r.structure.description_it.strip(), []).append(r)
    return sorted((Sede(g) for g in gruppi.values()), key=lambda s: s.slug)


def trova_sede(nome_slug):
    """
    Sede con quello slug nella lingua attiva o, in mancanza, nell'altra (chi chiama rimanda al canonico).
    Come per le prestazioni, se non è più nei dati si usa la sua ultima pubblicazione.
    """
    strutture = list(Structure.objects.all())
    for slug_di in (lambda s: {s.sede_slug}, lambda s: s.sede_slug_lingue):
        nome = next((s.description_it.strip() for s in strutture if nome_slug in slug_di(s)), None)
        if nome is not None:
            break
    else:
        return None
    ids = [s.pk for s in strutture if s.description_it.strip() == nome]
    qs = WaitingRecord.objects.filter(structure__in=ids)
    records = list(qs.filter(publish_date=qs.aggregate(Max("publish_date"))["publish_date__max"])
                   .select_related("structure"))
    return Sede(records) if records else None
