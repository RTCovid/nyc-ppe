from datetime import date
from typing import NamedTuple, Dict

from ppe import models
from ppe.data_mapping.types import ImportedRow, repr_no_raw, DataFile
from ppe.data_mapping.utils import (
    parse_int,
    parse_date,
    ErrorCollector, parse_bool,
)
from ppe.dataclasses import Item, OrderType
from xlsx_utils import SheetMapping, Mapping


class VentilatorRow(ImportedRow, NamedTuple):
    type: str
    functionality: str
    vendor: str
    quantity: int

    eta: date

    delivered: bool

    raw_data: Dict[str, any]

    def __repr__(self):
        # return super().repr_no_raw()
        return repr_no_raw(self)

    def to_objects(self, error_collector: ErrorCollector):
        if self.delivered:
            return []

        if self.eta is None:
            return []

        if self.functionality in {'FULL', 'CRITICAL CARE'}:
            item = Item.ventilators_full_service
        elif self.functionality == 'LIMITED':
            item = Item.ventilators_non_full_service
        else:
            error_collector.report_error(f'Unknown ventilator type: {self.functionality}')
            return []

        if self.delivered:
            received_quantity = self.quantity
        else:
            received_quantity = 0

        purchase = models.Purchase(
            order_type=OrderType.Purchase,
            item=item,
            quantity=self.quantity,
            received_quantity=received_quantity,
            description=f'Ventilator {self.type} ({self.functionality})',
            raw_data=self.raw_data
        )
        deliveries = []
        if self.eta is not None:
            deliveries.append(
                models.ScheduledDelivery(
                    purchase=purchase,
                    delivery_date=self.eta,
                    quantity=self.quantity
                )
            )

        return [purchase, *deliveries]


HNH_VENTS = SheetMapping(
    sheet_name='H+H 4-3 3PM',
    data_file=DataFile.PPE_ORDERINGCHARTS_DATE_XLSX,
    mappings={
        Mapping(
            sheet_column_name='Type',
            obj_column_name='type',
        ),
        Mapping(
            sheet_column_name='Adjusted ETA',
            obj_column_name='eta',
            proc=parse_date
        ),
        Mapping(
            sheet_column_name="Quantity",
            obj_column_name="quantity",
            proc=parse_int,
        ),
        Mapping(
            sheet_column_name='Functionality',
            obj_column_name='functionality'
        ),
        Mapping(sheet_column_name="Vendor", obj_column_name="vendor"),
        Mapping(sheet_column_name="Delivered?", obj_column_name="delivered", proc=parse_bool),
    },
    include_raw=True,
    obj_constructor=VentilatorRow,
)
