from django.contrib import admin
from .models import DataFetchLog, Structure, WaitingRecord


@admin.register(WaitingRecord)
class WaitingRecordAdmin(admin.ModelAdmin):
    list_display = (
        "activity_code", "activity_description_it", "waiting_days",
          "publish_date", "fetched_at", "structure__description_it"
    )
    list_filter = ("priority_list", "publish_date")
    search_fields = ("activity_description_it", "activity_code", "structure__description_it")
    readonly_fields = ("fetched_at",)


@admin.register(DataFetchLog)
class DataFetchLogAdmin(admin.ModelAdmin):
    list_display = ("fetched_at", "new_records_count", "records_count", "latest_survey_date", "latest_publish_date")
    readonly_fields = ("fetched_at", "records_count", "new_records_count", "latest_survey_date", "latest_publish_date")


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ("description_it","address_name_it", "city_it")
    search_fields = ("description_it",)
    search_fields = ("description_it", "address_name")
