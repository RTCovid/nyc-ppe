from django.urls import path

from ppe import views

urlpatterns = [
    path("", views.default, name="index"),
    path("drilldown", views.drilldown, name="drilldown"),
    path("forecast/supply", views.supply_forecast, name="supply_forecast"),
    path("upload/", views.Upload.as_view(), name="upload"),
    path("verify/<str:import_id>/", views.Verify.as_view(), name="verify"),
    path("cancel/<str:import_id>/", views.CancelImport.as_view(), name="cancel")
]
