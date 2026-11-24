# Attese

Cruscotto pubblico per consultare i tempi di attesa delle prestazioni sanitarie in Provincia di
Bolzano/Alto Adige, a partire dai dati opendata pubblicati dalla Provincia.

Vedi anche [README.md](README.md) (uso, stack, avvio locale) e [DEPLOY.md](DEPLOY.md) (deploy
self-hosted e su Google Cloud Run).

## Obiettivo

- Ricerca pubblica libera (nessun login) per prestazione → strutture con le date più vicine.
- Import giornaliero automatico dai dati opendata (Celery beat in self-host, Cloud Scheduler + Cloud
  Run Job nel deploy su Cloud Run).
- Storico: ogni fetch è tracciato (`DataFetchLog`) per seguire l'andamento dei tempi medi nel tempo.

## Modello dati (app `attese`)

- `DataFetchLog` — un record per ogni esecuzione di `fetch_waitingtimes`, mai cancellato: numero
  record importati/nuovi, data ultima rilevazione/pubblicazione.
- `Structure` — struttura sanitaria (nome IT/DE, indirizzo, contatti), aggiornata dal management
  command.
- `WaitingRecord` — un record del dataset opendata (prestazione, giorni di attesa, struttura,
  date), aggiornato dal management command.

Nessun modello utente custom: l'accesso a `/django-admin/` usa allauth + Google OAuth, ma solo per
utenti già `is_staff=True` esistenti (vedi `accounts/adapters.py`) — non c'è registrazione pubblica.

## Lingue (italiano e tedesco)

- `i18n_patterns` con `prefix_default_language=False`: italiano senza prefisso, tedesco sotto `/de/` con
  percorsi tradotti nel `.po` (`/de/leistungen/…`, `/de/statistik/`). La lingua viene **solo dall'URL**:
  niente cambi automatici in base al browser o a cookie. `sitemap.xml` e `robots.txt` restano fuori.
- Testi sorgente in italiano (`{% translate %}`), tedesco in `locale/de/LC_MESSAGES/django.po`. Dopo ogni
  modifica: `makemessages -l de --no-location --no-wrap` (opzioni uguali in CI, che controlla che il
  `.po` sia aggiornato e completo). I `.mo` non si versionano: li compila il Dockerfile, in locale
  `compilemessages -l de`.
- Dati bilingui in `attese/lingue.py`: `Bilingue.testo()` sui modelli (`record.activity_description`,
  `structure.city`…) e `localizzato()` nelle query; se il tedesco manca si mostra l'italiano. `slug()`
  rende gli umlaut come `ae/oe/ue/ss`, solo in tedesco.
- `lingue_alternative` (context processor) alimenta hreflang e pulsante IT/DE; la pagina di una
  prestazione passa le proprie, perché cambia anche lo slug.
- Data stimata = **pubblicazione** + giorni di attesa (scelta del 24/11/2026). I dati escono circa una
  volta al mese: se la data è già passata è in grigio con la nota.

## Note specifiche del progetto

- **Rinominato da `waitimes`/`waittimes` ad `attese`** (rename completo: app Django, DB, immagine
  Docker, repo). Il vecchio repo privato `azuki-beans/waittimes` esiste ancora ma è stato
  abbandonato (conteneva un secret OAuth leakato in git history) — il repo attivo è
  `azuki-beans/attese`, branch `main`, storia partita pulita da zero.
- **DB switchabile**: `config/settings.py` usa Postgres di default, ma passa a SQLite se
  `DATABASE_ENGINE=sqlite` — usato solo per il deploy demo su Cloud Run (SQLite su volume GCS
  montato, `--max-instances 1` per via degli scrittori concorrenti). Il self-host via
  `stacks/stack-*.yml` resta sempre su Postgres/Celery/Redis, invariato.
- **GCP**: demo live su Cloud Run, progetto `waiting-list-497918` (nome visualizzato rinominato in
  "attese", ma l'ID progetto resta quello per via del client OAuth Google riutilizzato). Dettagli
  completi dell'infrastruttura in [DEPLOY.md](DEPLOY.md).
- **Stato repo**: **pubblico** su GitHub (`azuki-beans/attese`) dal 22/11/2026, dopo la
  riscrittura della storia (email dei commit solo `@gmail.com`, scansione gitleaks pulita). Tutto
  ciò che si committa è visibile a chiunque: mai dati personali, segreti o note su infrastrutture
  non legate al progetto.
- **Hosting attuale**: Cloud Run, servizio `attese` + job `attese-fetch`/`attese-migrate` in
  **`europe-west1`**; Cloud Scheduler `attese-fetch-daily` (06:00 Europe/Rome) in `europe-west3`.
  Env del servizio: `GUNICORN_WORKERS=1`, 512Mi (minimo per gen2).
- **Rilascio** (procedura completa in [DEPLOY.md](DEPLOY.md)):
  1. commit su `main`, poi `git tag vX.Y.Z && git push origin main vX.Y.Z` → la CI pubblica
     l'immagine su `ghcr.io` (usata solo dal self-host);
  2. Cloud Run non usa ghcr.io: build con `gcloud builds submit --region europe-west1 --config
     docker/cloudbuild.yaml --substitutions _TAG=vX.Y.Z .` (Artifact Registry), poi
     `gcloud run deploy attese --image …:vX.Y.Z` e `gcloud run jobs update` per i due job.
  `gcloud run deploy --source .` **non funziona** (Dockerfile in `docker/`, non in root).
- **Immagine**: multi-stage `python:3.14-slim` (Poetry solo nel builder), `.dockerignore` rigoroso,
  gunicorn gthread con `--preload` (`GUNICORN_WORKERS`/`GUNICORN_THREADS`). ~220 MB e ~160 MB di
  RAM, contro 1,4 GB / 350 MB della versione su `python:3.14` con 3 worker sync.
- **Identità git**: `user.email` è impostata in locale nel repo (diversa dal globale); account gh
  `marcotn`.
- **`stacks/`** non è versionata (tolta dal tracking in v0.1.0): attenzione a `git rebase`/checkout
  su commit vecchi, che la riportano o la cancellano dal disco.
- **Favicon**: marchio azuki-beans (da `p7m-apri/brand/favicon.svg`) in `static/images/`
  (SVG + PNG 32 + apple-touch-icon); `/favicon.ico` rimanda al PNG.
- **`.gcloudignore`**: senza, `gcloud builds submit` carica tutta la cartella nel bucket
  `waiting-list-497918_cloudbuild`, file locali non versionati compresi. Controllare con `gcloud meta list-files-for-upload .` prima di aggiungere file locali.
- **Chiavi del dataset**: le note sono in `infoit` (minuscolo) ma `infoDe` (camel case):
  `fetch_waitingtimes` le legge così.
- **Default sicuri**: senza env si parte con `DEBUG=0` e senza `SECRET_KEY` l'app non si avvia
  (in build il Dockerfile passa una chiave fittizia solo a `collectstatic`).
- **Email**: nessun invio, backend console (niente SMTP). Gli errori 500 vanno nei log.
- **Dominio custom** `attese.azukibeans.dev` attivo dal 16/08/2026: domain mapping Cloud Run
  (CNAME `attese → ghs.googlehosted.com`, certificato gestito da Google) con **proxy Cloudflare**
  davanti (zona `azukibeans.dev` su Cloudflare). La VPS Hetzner non serve più il dominio:
  eventuale stack residuo lì è da dismettere.
