set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

PORT="${PORT:-8000}"

if [ "$DEBUG" == "1" ]; then
  python manage.py runserver "0.0.0.0:$PORT"
else
  gunicorn --bind="0.0.0.0:$PORT" --workers=3 --max-requests=1000 --log-level=error config.wsgi:application
fi
