from django.urls import path

from ppe import views

urlpatterns = [
    path("", views.default, name="index"),
    path("drilldown", views.drilldown, name="drilldown")
]
