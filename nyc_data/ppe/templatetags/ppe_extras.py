from django import template

from ppe.aggregations import split_value_unit

register = template.Library()

def pretty_num(value):
    (value, unit) = split_value_unit(float(value))
    return f'{value}{unit}'

register.filter('pretty_num', pretty_num)