import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from attese.models import DataFetchLog, Structure, WaitingRecord


def _parse_date(value):
    if not value:
        return None
    try:
        return value[:10]  # "YYYY-MM-DD"
    except TypeError:
        return None


def _bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def fetch_and_import(stdout=None):
    """
    Scarica i dati JSON dall'opendata e li importa nel database.
    Ritorna il numero di record importati.
    Può essere chiamata anche da task Celery.
    """
    url = getattr(settings, "WAITINGTIMES_JSON_URL", "https://daten.buergernetz.bz.it/services/WaitLists_Data/json")

    if stdout:
        stdout.write(f"Connessione a {url} ...")

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()

    if stdout:
        stdout.write(f"Ricevuti {len(data)} record. Salvataggio nel database...")

    new_records = 0
    latest_survey_date = None
    latest_publish_date = None

    for item in data:
        if not item.get("structureDescriptionIt"):
            continue

        survey_date = _parse_date(item.get("SurveyDate"))
        publish_date = _parse_date(item.get("publishDate"))

        if survey_date and (latest_survey_date is None or survey_date > latest_survey_date):
            latest_survey_date = survey_date
        if publish_date and (latest_publish_date is None or publish_date > latest_publish_date):
            latest_publish_date = publish_date

        chiave = {
            "description_it": item.get("structureDescriptionIt") or "",
            "address_name_it": item.get("addressNameIt") or "",
            "street_it": item.get("streetIt") or "",
        }
        altri = {
            "description_de": item.get("structureDescriptionDe") or "",
            "address_name_de": item.get("addressNameDe") or "",
            "street_de": item.get("streetDe") or "",
            "zip": item.get("zip") or "",
            "city_it": item.get("cityIt") or "",
            "city_de": item.get("cityDe") or "",
            "phone": item.get("phone") or "",
            "mail_it": item.get("mailIt") or "",
            "mail_de": item.get("mailDe") or "",
            "opening_hours_de": item.get("openinghoursDe") or "",
        }
        structure = Structure.objects.filter(**chiave).first()
        if not structure:
            structure = Structure.objects.create(**chiave, **altri)
        else:
            # completa solo i campi ancora vuoti (es. aggiunti dopo il primo import)
            mancanti = [campo for campo, valore in altri.items() if valore and not getattr(structure, campo)]
            if mancanti:
                for campo in mancanti:
                    setattr(structure, campo, altri[campo])
                structure.save(update_fields=mancanti)

        exists = WaitingRecord.objects.filter(
            survey_date=survey_date,
            activity_code=item.get("activityCode"),
            publish_date=publish_date,
            structure=structure,
        ).exists()
        if not exists:
            WaitingRecord.objects.create(
                survey_date=survey_date,
                activity_code=item.get("activityCode") or "",
                activity_description_it=item.get("activityDescriptionIt") or "",
                activity_description_de=item.get("activityDescriptionDe") or "",
                structure=structure,
                waiting_days=item.get("waitingDays"),
                priority_list=_bool(item.get("priorityList", False)),
                info_it=item.get("infoit") or item.get("infoIt") or "",
                info_de=item.get("infoDe") or "",
                publish_date=publish_date,
            )
            new_records += 1

    if new_records > 0:
        DataFetchLog.objects.create(
            records_count=len(data),
            new_records_count=new_records,
            latest_survey_date=latest_survey_date,
            latest_publish_date=latest_publish_date,
        )

    return new_records


class Command(BaseCommand):
    help = "Preleva i tempi di attesa sanitari dall'opendata di Alto Adige/Südtirol e li importa nel database."

    def handle(self, *args, **options):
        try:
            count = fetch_and_import(stdout=self.stdout)
            self.stdout.write(self.style.SUCCESS(f"Importati {count} record con successo."))
        except requests.RequestException as exc:
            self.stderr.write(self.style.ERROR(f"Errore di rete: {exc}"))
            raise SystemExit(1)
        except Exception as exc:  # noqa: BLE001 - ultimo paracadute del comando
            self.stderr.write(self.style.ERROR(f"Errore imprevisto: {exc}"))
            raise SystemExit(1)
