from django.contrib.sitemaps.views import sitemap
from django.urls import path

from .sitemaps import sitemaps
from .views import (
    ActivityChartPartialView,
    ActivityDetailView,
    ActivityIndexView,
    DashboardView,
    FilterPartialView,
    ResultsPartialView,
    StatisticsView,
    StructureChartPartialView,
    StructurePickerPartialView,
    robots_txt,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("statistiche/", StatisticsView.as_view(), name="statistics"),
    path("prestazioni/", ActivityIndexView.as_view(), name="activity_index"),
    path("prestazioni/<str:code>/", ActivityDetailView.as_view(), name="activity_detail_short"),
    path("prestazioni/<str:code>/<slug:slug>/", ActivityDetailView.as_view(), name="activity_detail"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("partials/filter/", FilterPartialView.as_view(), name="filter_partial"),
    path("partials/results/", ResultsPartialView.as_view(), name="results_partial"),
    path("partials/chart/attivita/", ActivityChartPartialView.as_view(), name="activity_chart_partial"),
    path("partials/chart/struttura/", StructureChartPartialView.as_view(), name="structure_chart_partial"),
    path("partials/chart/struttura-picker/", StructurePickerPartialView.as_view(), name="structure_picker_partial"),
]
