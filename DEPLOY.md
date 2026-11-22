# Deploy

Due percorsi: un server proprio con Podman/Docker (stack completo con Postgres/Redis/Celery), o
Google Cloud Run per una demo pubblica a costo zero.

## Server proprio

Il progetto è pensato per girare dietro un reverse proxy (nginx, Caddy, Traefik...) che termina
l'HTTPS e inoltra a Django in HTTP. `config/settings.py` è già configurato per fidarsi
dell'header `X-Forwarded-Proto`.

1. Prepara uno `stacks/stack-prod.yml` (la cartella `stacks/` non è versionata) e crea un file `.env` accanto (vedi `.env.example` per la lista
   completa delle variabili: `SECRET_KEY`, `POSTGRES_PASSWORD`, `ALLOWED_HOSTS`,
   `GOOGLE_CLIENT_ID`/`SECRET`, `SITE_URL`, `CSRF_TRUSTED_ORIGINS`, ...).
2. Avvia lo stack:
   ```bash
   podman compose -f stacks/stack-prod.yml --env-file .env up -d
   ```
   Include Postgres, Redis, l'app web, Celery worker e Celery beat (che aggiorna i dati ogni
   giorno alle 06:00). Le immagini sono quelle pubblicate su `ghcr.io/azuki-beans/attese` dalla
   CI al push di un tag `v*` (`git tag v1.2.3 && git push origin v1.2.3`): ogni rilascio è
   taggato `1.2.3`, `1.2` e `latest`, e lo stack usa `:latest`.
   Il web gira con gunicorn gthread: `GUNICORN_WORKERS` (default 2) × `GUNICORN_THREADS`
   (default 4); il worker Celery usa `--concurrency=1` (c'è un solo task giornaliero).
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
REGION=europe-west1          # servizio web e job Cloud Run
SCHEDULER_REGION=europe-west3  # Cloud Scheduler (creato lì, funziona lo stesso cross-region)
BUCKET=attese-data

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com storage.googleapis.com cloudscheduler.googleapis.com \\
  cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
```

Segreti (una volta sola, poi si aggiornano con `gcloud secrets versions add`):

```bash
echo -n "..." | gcloud secrets create attese-secret-key --data-file=-
echo -n "..." | gcloud secrets create attese-google-client-id --data-file=-
echo -n "..." | gcloud secrets create attese-google-client-secret --data-file=-
```

### 2. Build dell'immagine

`docker/Dockerfile` non è in root, quindi `gcloud run deploy --source .` non lo trova (proverebbe
i buildpack e fallisce). Si builda con Cloud Build usando `docker/cloudbuild.yaml`, che pubblica
l'immagine su Artifact Registry come `:<tag>` e `:latest` — non dipende dalla visibilità del repo
GitHub né da `ghcr.io`. Cosa viene caricato su Cloud Build lo decide `.gcloudignore` (verificabile
con `gcloud meta list-files-for-upload .`):

```bash
TAG=v1.2.3   # lo stesso tag git del rilascio
IMAGE="$REGION-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/attese:$TAG"

gcloud builds submit --region "$REGION" --config docker/cloudbuild.yaml --substitutions _TAG="$TAG" .
```

### 3. Servizio web

Primo deploy (configurazione completa):

```bash
gcloud run deploy attese \
  --image "$IMAGE" \
  --region "$REGION" \
  --execution-environment gen2 \
  --memory 512Mi --cpu 1 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --max-instances 1 \
  --set-env-vars "^;^DEBUG=0;GUNICORN_WORKERS=1;DATABASE_ENGINE=sqlite;SQLITE_PATH=/data/db.sqlite3;ALLOWED_HOSTS=.run.app,attese.azukibeans.dev;SITE_URL=https://attese.azukibeans.dev;CSRF_TRUSTED_ORIGINS=https://attese.azukibeans.dev" \
  --set-secrets SECRET_KEY=attese-secret-key:latest,GOOGLE_CLIENT_ID=attese-google-client-id:latest,GOOGLE_CLIENT_SECRET=attese-google-client-secret:latest \
  --allow-unauthenticated
```

`^;^` cambia il separatore delle variabili (`ALLOWED_HOSTS` contiene una virgola).
`GUNICORN_WORKERS=1`: con SQLite e una sola istanza basta un processo gunicorn (gthread, 4 thread),
~1/3 della RAM rispetto ai vecchi 3 worker sync. `512Mi` è il minimo consentito da gen2 (che serve
per il volume Cloud Storage), quindi il limite non scende oltre.

Rilasci successivi (env, volume e segreti restano quelli già configurati):

```bash
gcloud run deploy attese --image "$IMAGE" --region "$REGION"
gcloud run jobs update attese-fetch --image "$IMAGE" --region "$REGION"
gcloud run jobs update attese-migrate --image "$IMAGE" --region "$REGION"
```

Le migrazioni girano anche all'avvio del container (`boot.sh`); il job `attese-migrate` serve per
lanciarle esplicitamente prima del primo deploy o dopo una migration delicata:

```bash
gcloud run jobs deploy attese-migrate \
  --image "$IMAGE" \
  --region "$REGION" \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --set-env-vars DATABASE_ENGINE=sqlite,SQLITE_PATH=/data/db.sqlite3 \
  --command python --args manage.py,migrate

gcloud run jobs execute attese-migrate --region "$REGION" --wait
```

### 4. Import giornaliero (Cloud Run Job + Cloud Scheduler)

```bash
gcloud run jobs deploy attese-fetch \
  --image "$IMAGE" \
  --region "$REGION" \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/data \
  --set-env-vars DATABASE_ENGINE=sqlite,SQLITE_PATH=/data/db.sqlite3 \
  --command python --args manage.py,fetch_waitingtimes

gcloud scheduler jobs create http attese-fetch-daily \
  --location "$SCHEDULER_REGION" \
  --schedule "0 6 * * *" \
  --time-zone "Europe/Rome" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/attese-fetch:run" \
  --http-method POST \
  --oauth-service-account-email "SCHEDULER_SA@$PROJECT.iam.gserviceaccount.com"
```

### 5. Dominio custom, Cloudflare e login Google

Stato attuale: `attese.azukibeans.dev` è mappato al servizio (attivo dal 16/08/2026) e servito
dietro il proxy Cloudflare.

1. Mappa il dominio al servizio con
   [`gcloud beta run domain-mappings create`](https://cloud.google.com/run/docs/mapping-custom-domains):
   ```bash
   gcloud beta run domain-mappings create --service attese --domain attese.azukibeans.dev \
     --region "$REGION"
   ```
2. Su Cloudflare (zona `azukibeans.dev`) crea il record indicato dal mapping:
   `CNAME attese → ghs.googlehosted.com`, con proxy attivo (nuvola arancione).
   Impostare **SSL/TLS → Full (strict)**: con *Flexible* Cloudflare parla in HTTP con Google e si
   rischiano loop di redirect e redirect URI OAuth in `http://`.
   Se il certificato Google non si emette/rinnova, mettere temporaneamente il record in *DNS only*
   finché `gcloud beta run domain-mappings describe` non mostra `CertificateProvisioned: True`.
3. Registra `https://attese.azukibeans.dev/accounts/google/login/callback/` come URI di redirect
   autorizzato sul client OAuth Google (Google Cloud Console → Credentials).

### Limiti di questo setup

- Un solo scrittore SQLite alla volta (`--max-instances 1`): va bene per una demo a basso
  traffico, non per un servizio con carico serio.
- Nessun failover/replica: il bucket è comunque versionabile e va bene per un progetto
  amatoriale, non per dati critici.
- Se in futuro serve scalare, il passo naturale è passare a Postgres (Cloud SQL, a pagamento, o un
  provider gestito esterno) rimuovendo `DATABASE_ENGINE=sqlite`.
