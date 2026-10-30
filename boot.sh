set -e

python manage.py migrate --noinput

PORT="${PORT:-8000}"

if [ "$DEBUG" == "1" ]; then
  exec python manage.py runserver "0.0.0.0:$PORT"
else
  # gthread: pochi processi e più thread ciascuno -> RAM ~ proporzionale ai worker.
  # --preload carica l'app una volta nel master e la condivide (copy-on-write).
  # Su Cloud Run (SQLite, una sola istanza) basta GUNICORN_WORKERS=1.
  exec gunicorn --bind="0.0.0.0:$PORT" \
    --worker-class=gthread \
    --workers="${GUNICORN_WORKERS:-2}" \
    --threads="${GUNICORN_THREADS:-4}" \
    --max-requests=1000 --max-requests-jitter=100 \
    --worker-tmp-dir=/dev/shm \
    --preload --log-level=error config.wsgi:application
fi
