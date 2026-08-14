# Deploy

Due percorsi: un server proprio con Podman/Docker (stack completo con Postgres/Redis/Celery), o
Google Cloud Run per una demo pubblica a costo zero.

## Server proprio

Il progetto è pensato per girare dietro un reverse proxy (nginx, Caddy, Traefik...) che termina
l'HTTPS e inoltra a Django in HTTP. `config/settings.py` è già configurato per fidarsi
dell'header `X-Forwarded-Proto`.

1. Copia `stacks/stack-prod.yml` e crea un file `.env` accanto (vedi `.env.example` per la lista
   completa delle variabili: `SECRET_KEY`, `POSTGRES_PASSWORD`, `ALLOWED_HOSTS`,
   `GOOGLE_CLIENT_ID`/`SECRET`, SMTP, `SITE_URL`, `CSRF_TRUSTED_ORIGINS`, ...).
2. Avvia lo stack:
   ```bash
   podman compose -f stacks/stack-prod.yml --env-file .env up -d
   ```
   Include Postgres, Redis, l'app web, Celery worker e Celery beat (che aggiorna i dati ogni
   giorno alle 06:00). Le immagini sono quelle pubblicate su `ghcr.io/azuki-beans/attese` dalla
   CI a ogni push su `main`.
3. Configura il reverse proxy per inoltrare a `attese:8000` (nome del servizio nello stack),
   impostando `X-Forwarded-Proto` e `Host`:
   ```nginx
   location / {
       proxy_pass http://attese:8000;
       proxy_set_header Host              $host;
       proxy_set_header X-Forwarded-Proto  $scheme;
       proxy_set_header X-Forwarded-Host   $host;
   }
   ```
4. Registra l'URI di redirect HTTPS pubblico (`https://tuodominio/accounts/google/login/callback/`)
   sul client OAuth Google.

## Google Cloud Run (demo gratuita)

Il container si adatta automaticamente alla variabile `$PORT` iniettata da Cloud Run (default
8000 se non impostata).

Su Cloud Run **non si usano Postgres/Redis/Celery**: costerebbero (Cloud SQL non ha un free tier
stabile) o non hanno senso su un servizio che scala a zero. Al loro posto:

- **Database**: SQLite su un volume [Cloud Storage montato come filesystem](https://cloud.google.com/run/docs/configuring/services/storage-volume-mounts)
  (richiede `--execution-environment gen2`). Resta dentro l'Always Free Tier di Cloud Storage
  (5 GB gratis, ben oltre quanto serve). Il servizio va limitato a **`--max-instances 1`**: SQLite
  su un filesystem di rete non gestisce bene più scrittori concorrenti, e con un solo scrittore
  alla volta (le sessioni admin, poco traffico da demo) non è un problema.
- **Import giornaliero dati**: invece di Celery beat, un **Cloud Run Job** schedulato da
  **Cloud Scheduler**, che lancia `python manage.py fetch_waitingtimes` una volta al giorno.

Il codice legge la variabile `DATABASE_ENGINE=sqlite` per passare da Postgres (default) a SQLite
(vedi `config/settings.py`).

### 1. Setup una tantum

```bash
PROJECT=waiting-list-497918   # progetto GCP esistente, già usato per questo servizio
REGION=europe-west3
BUCKET=attese-data

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com storage.googleapis.com cloudscheduler.googleapis.com

gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
```

Segreti (una volta sola, poi si aggiornano con `gcloud secrets versions add`):

```bash
echo -n "..." | gcloud secrets create attese-secret-key --data-file=-
echo -n "..." | gcloud secrets create attese-google-client-id --data-file=-
echo -n "..." | gcloud secrets create attese-google-client-secret --data-file=-
```

### 2. Servizio web

```bash
gcloud run deploy attese \
  --source . \
  --region "$REGION" \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --max-instances 1 \
  --set-env-vars DEBUG=0,DATABASE_ENGINE=sqlite,SQLITE_PATH=/data/db.sqlite3,ALLOWED_HOSTS=attese.azukibeans.dev,SITE_URL=https://attese.azukibeans.dev,CSRF_TRUSTED_ORIGINS=https://attese.azukibeans.dev \
  --set-secrets SECRET_KEY=attese-secret-key:latest,GOOGLE_CLIENT_ID=attese-google-client-id:latest,GOOGLE_CLIENT_SECRET=attese-google-client-secret:latest \
  --allow-unauthenticated
```

`--source .` fa buildare l'immagine a Cloud Build e la pubblica su Artifact Registry — non dipende
dalla visibilità del repo GitHub né da `ghcr.io`.

Migrazioni al primo deploy (e a ogni nuova migration):

```bash
gcloud run jobs deploy attese-migrate \
  --source . \
  --region "$REGION" \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --set-env-vars DATABASE_ENGINE=sqlite,SQLITE_PATH=/data/db.sqlite3 \
  --command python --args manage.py,migrate

gcloud run jobs execute attese-migrate --region "$REGION" --wait
```

### 3. Import giornaliero (Cloud Run Job + Cloud Scheduler)

```bash
gcloud run jobs deploy attese-fetch \
  --source . \
  --region "$REGION" \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --set-env-vars DATABASE_ENGINE=sqlite,SQLITE_PATH=/data/db.sqlite3 \
  --command python --args manage.py,fetch_waitingtimes

gcloud scheduler jobs create http attese-fetch-daily \
  --location "$REGION" \
  --schedule "0 6 * * *" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/attese-fetch:run" \
  --http-method POST \
  --oauth-service-account-email "SCHEDULER_SA@$PROJECT.iam.gserviceaccount.com"
```

### 4. Dominio custom e login Google

1. Mappa `attese.azukibeans.dev` al servizio con
   [`gcloud run domain-mappings create`](https://cloud.google.com/run/docs/mapping-custom-domains).
2. Registra `https://attese.azukibeans.dev/accounts/google/login/callback/` come URI di redirect
   autorizzato sul client OAuth Google (Google Cloud Console → Credentials).

### Limiti di questo setup

- Un solo scrittore SQLite alla volta (`--max-instances 1`): va bene per una demo a basso
  traffico, non per un servizio con carico serio.
- Nessun failover/replica: il bucket è comunque versionabile e va bene per un progetto
  amatoriale, non per dati critici.
- Se in futuro serve scalare, il passo naturale è passare a Postgres (Cloud SQL, a pagamento, o un
  provider gestito esterno) rimuovendo `DATABASE_ENGINE=sqlite`.
