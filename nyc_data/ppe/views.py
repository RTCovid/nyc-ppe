from datetime import datetime, timedelta, date
from typing import NamedTuple, Optional, Callable, Set

from django.conf import settings
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
from ppe.aggregations import DemandCalculationConfig, AggColumn
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
    supply_components: Set[AggColumn]

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
        # Python defaults to Monday. Subtract one extra day to get us to Sunday
        default_start = datetime.today() + timedelta(weeks=1) - timedelta(days=datetime.today().weekday() + 1)
        default_end = default_start + timedelta(days=6)
        start_date = (parse_date(start_date, err_collector) or default_start).date()
        end_date = (
            parse_date(end_date, err_collector) or default_end
        ).date()

        if params.get("rollup") in {"mayoral", "", None}:
            rollup_fn = mayoral_rollup
        else:
            rollup_fn = lambda x: x

        if params.get("supply"):
            supply_components = {
                AggColumn(col) for col in params.get("supply").split(",")
            }
        else:
            supply_components = AggColumn.all()

        print(f"Parsed request as {start_date}->{end_date}")
        if len(err_collector) > 0:
            err_collector.dump()
        return StandardRequestParams(
            start_date=start_date,
            end_date=end_date,
            rollup_fn=rollup_fn,
            supply_components=supply_components,
        )


@login_required
def default(request):
    params = StandardRequestParams.load_from_request(request)

    aggregation = aggregations.asset_rollup(
        time_range=params.time_range(),
        supply_cols=params.supply_components,
        demand_calculation_config=DemandCalculationConfig(rollup_fn=params.rollup_fn),
    )

    cleaned_aggregation = [
        rollup
        for rollup in list(aggregation.values())
        if not all([rollup._value_at(col) == 0 for col in AggColumn.all()])
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
        category,
        params.rollup_fn,
        time_range=params.time_range(),
        supply_cols=params.supply_components,
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

    def handle_upload_error(self, err: Exception) -> UploadContext:
        try:
            raise err
        except ppe.errors.ImportInProgressError as ex:
            upload_context = UploadContext(
                error="Import already in progress for this file type.",
                import_in_progress=ex.import_id,
            )
        except ppe.errors.NoMappingForFileError as ex:
            upload_context = UploadContext(
                error="We were unable to find an existing mapping for this file."
            )

        except ppe.errors.SheetNameMismatch as ex:
            upload_context = UploadContext(error=str(ex))
        except ppe.errors.CsvImportError as ex:
            upload_context = UploadContext(error=f"Error reading CSV file: {ex}.")
        except ppe.errors.PartialFile as ex:
            upload_context = UploadContext(error=str(ex))
        except ppe.errors.ColumnNameMismatch as ex:
            upload_context = UploadContext(error=str(ex))
        except Exception as ex:
            if settings.DEBUG:
                raise
            upload_context = UploadContext(
                error=f"There was an unknown error importing the file. {ex}"
            )

        return upload_context

    def post(self, request):
        form = forms.UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                import_obj = data_import.handle_upload(
                    f=request.FILES["file"],
                    user=request.user,
                    current_as_of=form.data["data_current"],
                )
                return HttpResponseRedirect(
                    reverse("verify", kwargs={"import_id": import_obj.id})
                )
            except Exception as ex:
                context = self.handle_upload_error(ex)
                context = context._replace(form=form)
                return render(request, "upload.html", context._asdict())
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
        data_import.finalize_import(DataImport.objects.get(id=import_id))
        return HttpResponseRedirect(reverse("index"))


class CancelImport(LoginRequiredMixin, View):
    def post(self, request, import_id):
        import_obj = DataImport.objects.get(id=import_id)
        import_obj.cancel()
        import_obj.save()
        return HttpResponseRedirect(reverse("upload"))
