from datetime import datetime, timedelta, date
from typing import NamedTuple, Optional, Callable

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import Form
from django.http import HttpResponse, HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django_tables2 import RequestConfig

import ppe.errors
from ppe import aggregations, dataclasses as dc
from ppe import forms, data_import
from ppe.data_mapping.utils import parse_date, ErrorCollector
from ppe.drilldown import drilldown_result
from ppe.models import DataImport
from ppe.optimization import generate_forecast


def mayoral_rollup(row: str):
    return dc.Item(row).to_mayoral_category()


class StandardRequestParams(NamedTuple):
    start_date: date  # usually today
    end_date: date  # usually today + n days
    rollup_fn: Callable[[str], str]

    def time_range(self):
        return dc.Period(self.start_date, self.end_date)

    @classmethod
    def load_from_request(cls, request) -> "StandardRequestParams":
        if request.GET:
            params = request.GET
        else:
            params = request.POST

        start_date = params.get("start_date")
        end_date = params.get("end_date")

        err_collector = ErrorCollector()
        start_date = (parse_date(start_date, err_collector) or datetime.now()).date()
        end_date = (
            parse_date(end_date, err_collector) or datetime.now() + timedelta(days=29)
        ).date()

        if params.get("rollup") in {"mayoral", "", None}:
            rollup_fn = mayoral_rollup
        else:
            rollup_fn = lambda x: x

        print(f"Parsed request as {start_date}->{end_date}")
        if len(err_collector) > 0:
            err_collector.dump()
        return StandardRequestParams(
            start_date=start_date, end_date=end_date, rollup_fn=rollup_fn
        )


@login_required
def default(request):
    params = StandardRequestParams.load_from_request(request)

    aggregation = aggregations.asset_rollup_legacy(
        time_start=params.start_date,
        time_end=params.end_date,
        rollup_fn=params.rollup_fn,
    )

    displayed_vals = ["donate", "sell", "make", "inventory"]
    cleaned_aggregation = [
        rollup
        for rollup in list(aggregation.values())
        if not all([getattr(rollup, val) == 0 for val in displayed_vals])
    ]

    table = aggregations.AggregationTable(cleaned_aggregation)
    RequestConfig(request).configure(table)
    context = {
        "aggregations": table,
        "days_in_view": dc.Period(params.start_date, params.end_date)
        .inclusive_length()
        .days,
    }
    return render(request, "dashboard.html", context)


@login_required
def drilldown(request):
    params = StandardRequestParams.load_from_request(request)
    category = request.GET.get("category")
    if category is None:
        return HttpResponse("Need an asset category param", status=400)

    drilldown_res = drilldown_result(
        category, params.rollup_fn, time_range=params.time_range()
    )
    table = aggregations.TotaledAggregationTable(drilldown_res.aggregation.values())
    RequestConfig(request).configure(table)
    purchases = drilldown_res.purchases
    deliveries = drilldown_res.scheduled_deliveries
    inventory = drilldown_res.inventory
    donations = drilldown_res.donations

    received_deliveries = sum([p.received_quantity or 0 for p in purchases])
    context = {
        "aggregations": table,
        "asset_category": category,
        # conversion to data class handles conversion to display names, etc.
        "purchases": purchases,
        "deliveries": deliveries,
        "inventory": inventory,
        "donations": donations,
        "donations_total": sum([d.quantity for d in donations]),
        "deliveries_past": received_deliveries,
        "deliveries_next_three": sum(
            [
                d.quantity
                for d in deliveries
                if datetime.now().date()
                <= d.delivery_date
                <= datetime.now().date() + timedelta(days=2)
            ]
        ),
        "deliveries_next_week": sum(
            [
                d.quantity
                for d in deliveries
                if datetime.now().date()
                <= d.delivery_date
                <= datetime.now().date() + timedelta(days=6)
            ]
        ),
        "deliveries_next_thirty": sum(
            [
                d.quantity
                for d in deliveries
                if datetime.now().date()
                <= d.delivery_date
                <= datetime.now().date() + timedelta(days=29)
            ]
        ),
        "scheduled_total": sum([d.quantity for d in deliveries]),
        "unscheduled_total": sum(
            [
                purch.unscheduled_quantity
                for purch in purchases
                if purch.unscheduled_quantity
            ]
        ),
        "facility_deliveries": {
            k: v
            for k, v in aggregations.deliveries_for_period(
                datetime.now().date() - timedelta(days=6), datetime.now().date()
            ).items()
            if params.rollup_fn(k) == category
        },
    }
    return render(request, "drilldown.html", context)


@login_required
def supply_forecast(request):
    category = request.GET.get("category")
    if category is None:
        return HttpResponse("Need an asset category param", status=400)

    start_date = datetime.strptime(
        request.GET.get("start_date"), "%Y%m%d"
    )  # e.g. 20200406
    end_date = datetime.strptime(request.GET.get("end_date"), "%Y%m%d")  # e.g. 20200430
    days = (end_date - start_date).days + 1

    # TODO Get inventory on the start date
    start_inventory = 0  # inventory available at the beginning of start date

    # TODO Get demand forecast between start and end date
    demand_forecast = []  # array of integers with size == days

    # TODO Get known supply arriving between start and end date
    known_supply = []  # array of integers with size == days

    forecasts = generate_forecast(
        start_date, start_inventory, demand_forecast, known_supply
    )
    resp = [forecast.to_dict() for forecast in forecasts]
    return JsonResponse(dict(category=category, forecast=resp))


class UploadContext(NamedTuple):
    form: Form = forms.UploadFileForm
    error: Optional[str] = None
    import_in_progress: Optional[str] = None


class Upload(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "upload.html", UploadContext()._asdict())

    def post(self, request):
        form = forms.UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                import_obj = data_import.handle_upload(
                    request.FILES["file"], form.data["name"], form.data["data_current"]
                )
                return HttpResponseRedirect(
                    reverse("verify", kwargs={"import_id": import_obj.id})
                )
            except ppe.errors.ImportInProgressError as ex:
                return render(
                    request,
                    "upload.html",
                    UploadContext(
                        error="Import already in progress for this file type",
                        import_in_progress=ex.import_id,
                    )._asdict(),
                )
            except ppe.errors.NoMappingForFileError as ex:
                return render(
                    request,
                    "upload.html",
                    UploadContext(error="No mapping found for this file")._asdict(),
                )
            except ppe.errors.CsvImportError as ex:
                return render(
                    request,
                    "upload.html",
                    UploadContext(error="Error reading in CSV file")._asdict(),
                )
        else:
            return render(
                request, "upload.html", UploadContext(error=form.errors)._asdict()
            )


class Verify(LoginRequiredMixin, View):
    def get(self, request, import_id):
        import_obj = DataImport.objects.get(id=import_id)
        return render(
            request,
            "verify_upload.html",
            dict(import_id=import_id, delta=import_obj.compute_delta()),
        )

    def post(self, request, import_id):
        data_import.complete_import(DataImport.objects.get(id=import_id))
        return HttpResponseRedirect(reverse("index"))


class CancelImport(LoginRequiredMixin, View):
    def post(self, request, import_id):
        import_obj = DataImport.objects.get(id=import_id)
        import_obj.cancel()
        import_obj.save()
        return HttpResponseRedirect(reverse("upload"))
