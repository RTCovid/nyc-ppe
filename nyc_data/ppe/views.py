from django.http import HttpResponse
from datetime import datetime, timedelta
from django.shortcuts import render

# Create your views here.

from django_tables2 import RequestConfig
from django.template import loader

from ppe import aggregations


def default(request):
    template = loader.get_template('index.html')
    aggregation = aggregations.asset_rollup(datetime.now() - timedelta(days=30), datetime.now())
    table = aggregations.AggregationTable(list(aggregation.values()))
    RequestConfig(request).configure(table)
    context = {
        'aggregations': table
    }
    return render(request, "index.html", context)
