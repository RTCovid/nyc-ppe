from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from django.forms import Form
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

from ppe import aggregations, dataclasses as dc, forms, data_import
from ppe.drilldown import deliveries_for_item
from ppe.models import DataImport


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
        "deliveries": [d.to_dataclass() for d in deliveries_for_item(category, rollup)]
    }
    return render(request, "drilldown.html", context)


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

