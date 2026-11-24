from django.urls import path
from django.utils.translation import gettext_lazy as _

from .views import (
    ActivityChartPartialView,
    ActivityDetailView,
    ActivityIndexView,
    DashboardView,
    FilterPartialView,
    StatisticsView,
    StructureChartPartialView,
    StructurePickerPartialView,
)

# incluse in i18n_patterns: italiano senza prefisso, tedesco sotto /de/ con i percorsi tradotti nel .po
urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path(_("statistiche/"), StatisticsView.as_view(), name="statistics"),
    path(_("prestazioni/"), ActivityIndexView.as_view(), name="activity_index"),
    path(_("prestazioni/<str:code>/"), ActivityDetailView.as_view(), name="activity_detail_short"),
    path(_("prestazioni/<str:code>/<slug:slug>/"), ActivityDetailView.as_view(), name="activity_detail"),
    path("partials/filter/", FilterPartialView.as_view(), name="filter_partial"),
    path("partials/chart/attivita/", ActivityChartPartialView.as_view(), name="activity_chart_partial"),
    path("partials/chart/struttura/", StructureChartPartialView.as_view(), name="structure_chart_partial"),
    path("partials/chart/struttura-picker/", StructurePickerPartialView.as_view(), name="structure_picker_partial"),
]
