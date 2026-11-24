# --- builder: risolve le dipendenze in un venv isolato -----------------------
# Poetry (e le sue dipendenze) restano qui: nell'immagine finale entra solo /venv.
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN pip install poetry && python -m venv /venv

# Poetry installa nel venv attivo indicato da VIRTUAL_ENV
ENV VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi --no-root \
  && rm -rf "$POETRY_CACHE_DIR"


# --- translations: .po -> .mo con gettext, che non entra nell'immagine finale ----
FROM python:3.14-slim AS translations

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY locale ./locale
RUN find locale -name '*.po' -exec sh -c 'msgfmt --check -o "${1%.po}.mo" "$1"' _ {} \;


# --- runtime -----------------------------------------------------------------
FROM python:3.14-slim

# Correzioni di sicurezza Debian arrivate dopo l'ultima build di python:*-slim
# (es. zlib1g CVE-2026-85091). Nessun pacchetto aggiuntivo.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# MALLOC_ARENA_MAX: limita le arene malloc di glibc per thread (gunicorn gthread),
# meno memoria frammentata/RSS per processo.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH" \
    MALLOC_ARENA_MAX=2

COPY --from=builder /venv /venv

WORKDIR /app

# Codice: cosa entra lo decide .dockerignore
COPY . .
COPY --from=translations /app/locale ./locale

# Chiave fittizia solo per collectstatic: quella vera arriva a runtime
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["/bin/bash", "/app/boot.sh"]
