from datetime import date
from typing import NamedTuple, Dict

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import (
    parse_int,
    parse_date,
    ErrorCollector,
    parse_bool,
)
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping, RegexMatch


class VentilatorRow(ImportedRow, NamedTuple):
    type: str
    functionality: str
    vendor: str
    quantity: int
    quantity_delivered: int

    eta: date

    delivered: str

    raw_data: Dict[str, any]

    def __repr__(self):
        return repr_no_raw(self)

    def to_objects(self, error_collector: ErrorCollector):
        if self.delivered == "Yes":
            return []

        if self.eta is None:
            return []

        if self.functionality in {"FULL", "CRITICAL CARE"}:
            item = Item.ventilators_full_service
        elif self.functionality == "LIMITED":
            item = Item.ventilators_non_full_service
        else:
            error_collector.report_error(
                f"Unknown ventilator type: {self.functionality}"
            )
            return []

        purchase = models.Purchase(
            order_type=OrderType.Purchase,
            item=item,
            quantity=self.quantity,
            received_quantity=self.quantity_delivered,
            description=f"Ventilator {self.type} ({self.functionality})",
            raw_data=self.raw_data,
        )
        deliveries = []
        if self.eta is not None:
            deliveries.append(
                models.ScheduledDelivery(
                    purchase=purchase, delivery_date=self.eta, quantity=self.quantity
                )
            )

        return [purchase, *deliveries]


HNH_VENTS = SheetMapping(
    sheet_name=RegexMatch("H\+H \d+-\d+ \d+[AP]M"),  # 'H+H 4-3 3PM',
    data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
    mappings={
        Mapping(sheet_column_name="Equipment Detail", obj_column_name="type",),
        Mapping(
            sheet_column_name="Adjusted ETA", obj_column_name="eta", proc=parse_date
        ),
        Mapping(
            sheet_column_name="Quantity Ordered",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name="Quantity Delivered",
            obj_column_name="quantity_delivered",
            proc=parse_int,
        ),
        Mapping(sheet_column_name="Functionality", obj_column_name="functionality"),
        Mapping(sheet_column_name="Supplier", obj_column_name="vendor"),
        Mapping(sheet_column_name="Delivered?", obj_column_name="delivered"),
    },
    include_raw=True,
    obj_constructor=VentilatorRow,
)
