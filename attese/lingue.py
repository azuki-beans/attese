"""Contenuti bilingui: i dati opendata hanno ogni testo in italiano e in tedesco."""

from django.conf import settings
from django.db.models import F, Value
from django.db.models.functions import Coalesce, NullIf
from django.utils.text import slugify
from django.utils.translation import get_language

# "ä" -> "ae": slugify da solo toglierebbe i puntini ("ärztlich" -> "arztlich")
_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def tedesco():
    return get_language() == "de"


def slug(testo):
    """Slug nella lingua attiva: in italiano resta quello di sempre (gli URL non cambiano)."""
    return slugify(testo.translate(_UMLAUT) if tedesco() else testo)


def localizzato(campo):
    """Espressione ORM: `<campo>_de` se la lingua attiva è il tedesco (e non è vuoto), altrimenti `<campo>_it`."""
    it = F(f"{campo}_it")
    return Coalesce(NullIf(F(f"{campo}_de"), Value("")), it) if tedesco() else it


class Bilingue:
    """Mixin per i modelli con campi `<campo>_it` / `<campo>_de`."""

    def testo(self, campo):
        it = getattr(self, f"{campo}_it").strip()
        return (getattr(self, f"{campo}_de").strip() or it) if tedesco() else it


def codici_lingua():
    return [codice for codice, _ in settings.LANGUAGES]
