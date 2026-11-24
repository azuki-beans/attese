# Attese

Cruscotto pratico per consultare i **tempi di attesa delle prestazioni sanitarie** in Provincia di
Bolzano/Alto Adige: cerchi una prestazione (es. "Prima visita oculistica") e vedi subito quali
strutture hanno le date più vicine, ordinate per giorni di attesa.

![Dashboard di Attese con i risultati di una ricerca](docs/screenshots/dashboard.jpg)

Se volete saltare direttamente ai dati senza dettagli tecnici:

https://attese.azukibeans.dev/

## Cosa fa

- Scarica automaticamente i dati opendata della Provincia di Bolzano
- Mostra, per ogni prestazione, le strutture con le date disponibili più vicine
- Tiene traccia nel tempo dell'andamento dei tempi medi di attesa, globale e per prestazione

## Lingue

Italiano (`/`) e tedesco (`/de/`). In locale le traduzioni vanno compilate:
`python manage.py compilemessages -l de`.

## Dati

I dati provengono dall'[Open Data Hub dell'Alto Adige](https://data.civis.bz.it/it/dataset/southtyrolean-healthservices-waitingtimes),
pubblicati dalla Provincia Autonoma di Bolzano sotto licenza CC Zero.

## ⚠️ Avvertenza

Questo progetto non ha nessuna affiliazione ufficiale con la Provincia di Bolzano o l'Azienda
Sanitaria dell'Alto Adige. **Non garantiamo la correttezza, la completezza o l'aggiornamento dei
dati mostrati.**

Per prenotare una prestazione o ottenere informazioni certe sui tempi di attesa, contatta
direttamente l'**Azienda Sanitaria dell'Alto Adige**:
- Sito: [www.sabes.it](https://www.sabes.it)
- CUP (prenotazioni): 0471 100 200

## Stack tecnico

- [Django](https://www.djangoproject.com/) 6 + [Celery](https://docs.celeryq.dev/) (aggiornamento dati giornaliero)
- [PostgreSQL](https://www.postgresql.org/) + [Redis](https://redis.io/) (broker Celery)
- [HTMX](https://htmx.org/) + [Bootstrap 5](https://getbootstrap.com/) + [Chart.js](https://www.chartjs.org/)
- [django-allauth](https://docs.allauth.org/) con Google OAuth per l'accesso all'area admin (nessuna
  registrazione pubblica: la ricerca è liberamente consultabile da chiunque, senza login)
- Container [Podman](https://podman.io/)/Docker, WSGI con [gunicorn](https://gunicorn.org/)

## Avvio in locale

Richiede [Podman](https://podman.io/) (o Docker) con il plugin compose.

```bash
git clone git@github.com:azuki-beans/attese.git
cd attese
podman compose -f stacks/stack-local.yml up -d --build
podman compose -f stacks/stack-local.yml exec web python manage.py migrate
podman compose -f stacks/stack-local.yml exec web python manage.py fetch_waitingtimes
```

L'app è su [http://localhost:8000](http://localhost:8000). `stacks/stack-local.yml` include già
Postgres, Redis, Celery (worker + beat, che aggiorna i dati ogni giorno alle 06:00) e
[Mailpit](https://github.com/axllent/mailpit) per intercettare le email in locale — non serve
configurare nulla per iniziare a usare l'app.

Per accedere all'area admin (`/django-admin/`) serve invece un client OAuth Google: vedi la sezione
[Login admin (Google OAuth)](#login-admin-google-oauth) più sotto.

### Test rapidi

```bash
podman compose -f stacks/stack-local.yml exec web python manage.py check
podman compose -f stacks/stack-local.yml exec web python manage.py test
```

## Login admin (Google OAuth)

L'accesso a `/django-admin/` è protetto da login Google, ma **accetta solo utenti già esistenti
con `is_staff=True`**: non crea nuovi account automaticamente (vedi `accounts/adapters.py`). Per
usarlo serve un client OAuth su [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials):

1. Crea un client OAuth 2.0 di tipo "Applicazione web".
2. URI di reindirizzamento autorizzato: `<SITE_URL>/accounts/google/login/callback/` (in locale
   `http://localhost:8000/accounts/google/login/callback/`).
3. Imposta `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` nel tuo `.env`/variabili d'ambiente.
4. Crea un superuser o uno staff user via `python manage.py createsuperuser` con la stessa email
   dell'account Google che userai per accedere.

## Deploy

Per le istruzioni di deploy — sia su un server proprio (Podman/Docker) sia su Google Cloud Run
come demo pubblica gratuita — vedi [DEPLOY.md](DEPLOY.md).

## Licenza

Distribuito con licenza Apache 2.0 — vedi [LICENSE](LICENSE).

## Contribuire

Pull request e segnalazioni di bug sono benvenute.
