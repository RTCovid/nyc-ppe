from django import template

from ppe.aggregations import split_value_unit
from ppe.dataclasses import Item, MayoralCategory

register = template.Library()


def pretty_num(value):
    (value, unit) = split_value_unit(value)
    return f"{value}{unit}"


def display_name(value):
    try:
        return MayoralCategory(value).value
    except ValueError:
        pass

    try:
        return Item(value).display()
    except ValueError:
        pass
    # we give up
    return value


register.filter("pretty_num", pretty_num)
register.filter("display_name", display_name)
