from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from django.http import HttpResponse, JsonResponse
from django.forms import Form
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from ppe import aggregations, dataclasses as dc
from ppe import forms, data_import
from ppe.drilldown import drilldown_result
from ppe.models import DataImport
from ppe.optimization import generate_forecast


def mayoral_rollup(row):
    return row.to_mayoral_category()


def default(request):
    if request.GET.get('rollup') == 'mayoral':
        aggregation = aggregations.asset_rollup(
            datetime.now(), datetime.now() + timedelta(days=30),
            mayoral_rollup
        )
    else:
        aggregation = aggregations.asset_rollup(
            datetime.now(), datetime.now() + timedelta(days=30)
        )
    table = aggregations.AggregationTable(list(aggregation.values()))
    RequestConfig(request).configure(table)
    context = {"aggregations": table}
    return render(request, "dashboard.html", context)


def drilldown(request):
    category = request.GET.get('category')
    if category is None:
        return HttpResponse("Need an asset category param", status=400)
    if request.GET.get('rollup') == 'mayoral':
        rollup = mayoral_rollup
        cat_display = category
    else:
        rollup = lambda x: x
        cat_display = dc.Item(category).display()

    context = {
        "asset_category": cat_display,
        # conversion to data class handles conversion to display names, etc.
        "purchases": [p.to_dataclass() for p in drilldown_result(category, rollup)]
    }
    return render(request, "drilldown.html", context)


def supply_forecast(request):
    category = request.GET.get('category')
    if category is None:
        return HttpResponse("Need an asset category param", status=400)

    start_date = datetime.strptime(request.GET.get('start_date'), '%Y%m%d')  # e.g. 20200406
    end_date = datetime.strptime(request.GET.get('end_date'), '%Y%m%d')  # e.g. 20200430
    days = (end_date - start_date).days + 1

    # TODO Get inventory on the start date
    start_inventory = 0  # inventory available at the beginning of start date

    # TODO Get demand forecast between start and end date
    demand_forecast = []  # array of integers with size == days

    # TODO Get known supply arriving between start and end date
    known_supply = []  # array of integers with size == days

    forecasts = generate_forecast(start_date,
                                  start_inventory,
                                  demand_forecast,
                                  known_supply)
    resp = [forecast.to_dict() for forecast in forecasts]
    return JsonResponse(dict(category=category, forecast=resp))


class UploadContext(NamedTuple):
    form: Form = forms.UploadFileForm
    error: Optional[str] = None
    import_in_progress: Optional[str] = None


class Upload(View):
    def get(self, request):
        return render(request, "upload.html", UploadContext()._asdict())

    def post(self, request):
        form = forms.UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                import_obj = data_import.handle_upload(request.FILES['file'])
                return HttpResponseRedirect(reverse('verify', kwargs={"import_id": import_obj.id}))
            except data_import.ImportInProgressError as ex:
                return render(request, "upload.html",
                              UploadContext(error="Import already in progress for this file type",
                                            import_in_progress=ex.import_id)._asdict())


class Verify(View):
    def get(self, request, import_id):
        import_obj = DataImport.objects.get(id=import_id)
        return render(request, "verify_upload.html", dict(import_id=import_id, delta=import_obj.compute_delta()))

    def post(self, request, import_id):
        data_import.complete_import(DataImport.objects.get(id=import_id))
        return HttpResponseRedirect(reverse('index'))

class CancelImport(View):
    def post(self, request, import_id):
        import_obj = DataImport.objects.get(id=import_id)
        import_obj.cancel()
        import_obj.save()
        return HttpResponseRedirect(reverse('upload'))
