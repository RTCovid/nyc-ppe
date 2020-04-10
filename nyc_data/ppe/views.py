# Create your views here.

from datetime import datetime, timedelta

from django.shortcuts import render
from django_tables2 import RequestConfig

from ppe import aggregations


# Create your views here.


def default(request):
    if request.GET.get('rollup') == 'mayoral':
        aggregation = aggregations.asset_rollup(
            datetime.now(), datetime.now() + timedelta(days=30),
            lambda row: row.to_mayoral_category()
        )
    else:
        aggregation = aggregations.asset_rollup(
            datetime.now(), datetime.now() + timedelta(days=30)
        )
    table = aggregations.AggregationTable(list(aggregation.values()))
    RequestConfig(request).configure(table)
    context = {"aggregations": table}
    return render(request, "dashboard.html", context)
