from django.urls import path
from .views import AccessRequestView

urlpatterns = [
    path("request-access/", AccessRequestView.as_view(), name="access_request"),
]
