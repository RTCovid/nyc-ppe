# Create your views here.

from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django_tables2 import RequestConfig

from ppe import aggregations, dataclasses as dc
from ppe.drilldown import deliveries_for_item
from ppe.optimization import generate_forecast


# Create your views here.

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