from django.urls import path
from .views import (
    ActivityChartPartialView,
    DashboardView,
    FilterPartialView,
    ResultsPartialView,
    StatisticsView,
    StructureChartPartialView,
    StructurePickerPartialView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("statistiche/", StatisticsView.as_view(), name="statistics"),
    path("partials/filter/", FilterPartialView.as_view(), name="filter_partial"),
    path("partials/results/", ResultsPartialView.as_view(), name="results_partial"),
    path("partials/chart/attivita/", ActivityChartPartialView.as_view(), name="activity_chart_partial"),
    path("partials/chart/struttura/", StructureChartPartialView.as_view(), name="structure_chart_partial"),
    path("partials/chart/struttura-picker/", StructurePickerPartialView.as_view(), name="structure_picker_partial"),
]
