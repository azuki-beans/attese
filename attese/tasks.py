from celery import shared_task


@shared_task
def fetch_waitingtimes():
    from attese.management.commands.fetch_waitingtimes import fetch_and_import
    count = fetch_and_import()
    return f"Importati {count} record."
