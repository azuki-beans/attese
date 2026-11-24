import re
from datetime import timedelta

from django.db import models
from django.utils import timezone

from .lingue import Bilingue, slug

# CUP provinciale: nell'opendata compare quasi sempre senza prefisso ("100 100")
TELEFONO_CUP = "0471 100 100"


class DataFetchLog(models.Model):
    """
    Traccia ogni importazione dei dati opendata.
    Un record per ogni esecuzione di fetch_waitingtimes, mai cancellati.
    """
    fetched_at = models.DateTimeField(auto_now_add=True, verbose_name="Importato il", db_index=True)
    records_count = models.IntegerField(default=0, verbose_name="Record nel dataset")
    new_records_count = models.IntegerField(default=0, verbose_name="Nuovi record importati")
    latest_survey_date = models.DateField(null=True, blank=True, verbose_name="Data ultima rilevazione")
    latest_publish_date = models.DateField(null=True, blank=True, verbose_name="Data ultima pubblicazione opendata")

    class Meta:
        verbose_name = "Log importazione"
        verbose_name_plural = "Log importazioni"
        ordering = ["-fetched_at"]

    def __str__(self):
        return f"Fetch {self.fetched_at:%Y-%m-%d %H:%M} – {self.new_records_count} nuovi record"


class Structure(Bilingue, models.Model):
    """
    Una struttura sanitaria dell'Alto Adige.
    Viene aggiornata tramite il management command fetch_waitingtimes.
    """
    description_it = models.CharField(max_length=300, verbose_name="Struttura (IT)", db_index=True)
    description_de = models.CharField(max_length=300, verbose_name="Struktur (DE)", blank=True)
    address_name_it = models.CharField(max_length=300, blank=True, verbose_name="Reparto (IT)")
    address_name_de = models.CharField(max_length=300, blank=True, verbose_name="Abteilung (DE)")
    street_it = models.CharField(max_length=200, blank=True, verbose_name="Via (IT)")
    street_de = models.CharField(max_length=200, blank=True, verbose_name="Straße (DE)")
    zip = models.CharField(max_length=10, blank=True, verbose_name="CAP")
    city_it = models.CharField(max_length=100, blank=True, verbose_name="Città (IT)")
    city_de = models.CharField(max_length=100, blank=True, verbose_name="Stadt (DE)")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefono")
    mail_de = models.EmailField(blank=True, verbose_name="Email (DE)")
    mail_it = models.EmailField(blank=True, verbose_name="Email (IT)")
    opening_hours_de = models.TextField(blank=True, verbose_name="Orari di apertura (DE)")

    class Meta:
        verbose_name = "Struttura sanitaria"
        verbose_name_plural = "Strutture sanitarie"
        ordering = ["description_it"]

    def __str__(self):
        return self.description_it

    @property
    def description(self):
        return self.testo("description")

    @property
    def phone_number(self):
        """Telefono da mostrare: il CUP è completato col prefisso, gli altri restano come nei dati."""
        return TELEFONO_CUP if re.sub(r"\D", "", self.phone) == "100100" else self.phone

    @property
    def phone_link(self):
        """Solo cifre del primo numero, per `tel:` (nei dati ci sono "0473/735020" e "0474 581136 - 581137")."""
        return re.sub(r"\D", "", self.phone_number.split(" - ")[0])

    @property
    def address_name(self):
        return self.testo("address_name")

    @property
    def street(self):
        return self.testo("street")

    @property
    def city(self):
        return self.testo("city")


class WaitingRecord(Bilingue, models.Model):
    """
    Un record dal dataset opendata dei tempi di attesa sanitari dell'Alto Adige.
    Viene aggiornato tramite il management command fetch_waitingtimes.
    """
    survey_date = models.DateField(null=True, blank=True, verbose_name="Data rilevazione")
    activity_code = models.CharField(max_length=30, verbose_name="Codice prestazione", db_index=True)
    activity_description_it = models.CharField(max_length=300, verbose_name="Prestazione (IT)")
    activity_description_de = models.CharField(max_length=300, verbose_name="Leistung (DE)", blank=True)
    waiting_days = models.IntegerField(null=True, blank=True, verbose_name="Giorni di attesa")
    priority_list = models.BooleanField(default=False, verbose_name="Lista priorità")
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE, related_name="waiting_records", verbose_name="Struttura sanitaria")
    info_it = models.TextField(blank=True, verbose_name="Note (IT)")
    info_de = models.TextField(blank=True, verbose_name="Hinweise (DE)")
    publish_date = models.DateField(null=True, blank=True, verbose_name="Data pubblicazione")
    fetched_at = models.DateTimeField(auto_now_add=True, verbose_name="Importato il")

    class Meta:
        verbose_name = "Tempo di attesa"
        verbose_name_plural = "Tempi di attesa"
        ordering = ["activity_code", "waiting_days"]
        unique_together = ('survey_date', 'activity_code', 'publish_date', 'structure')

    def __str__(self):
        return f"{self.activity_description_it} – {self.structure.description_it}"

    @property
    def estimated_date(self):
        """Stima: oggi + giorni di attesa rilevati (i dati escono circa una volta al mese)."""
        if self.waiting_days is None:
            return None
        return timezone.localdate() + timedelta(days=self.waiting_days)

    @property
    def activity_description(self):
        return self.testo("activity_description")

    @property
    def activity_slug(self):
        return slug(self.activity_description)

    @property
    def info(self):
        return self.testo("info")
