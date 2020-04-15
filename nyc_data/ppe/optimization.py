from ortools.linear_solver import pywraplp
from datetime import timedelta, datetime, date
import ppe.dataclasses as dc
from ppe import aggregations
from ppe.aggregations import compute_scaling_factor, DemandCalculationConfig
from ppe.dataclasses import Forecast

# For each day and each type of resource, I am think of modeling with the following four variables (day N):
# demand_N : demand of this day.
# supply_N : known source of supply arriving on this day (will become available for the next day, N+1).
# additional_supply_N : manually input additional source of supply arriving on this day (will become available for the next day, N+1).
# inventory_N : inventory of this type of resource at the end of the day. If negative, it will indicate a shortage.

# demand_N  will be estimated from hospitalization projection and the per patient consumption rate.
# supply_N  will come from their data.
# additional_supply_N  will be part of the manual input from the user (maybe Dan?). They can plug in different numbers to examine different procurement startegy.
# inventory_N  will be estimated by the LP model.

# The type of constraints would be very simple at the beginning: just day-to-day consistency: inventory_N + supply_N + additional_supply_N - demand_(N+1) = inventory_(N+1)
from ppe.models import Inventory, ScheduledDelivery


def generate_forecast_for_item(start_date: date, item: dc.Item, n_days: int = 100):
    demand_data = aggregations.known_recent_demand()
    if item not in demand_data:
        return None
    else:
        demand_for_asset = demand_data[item]
    start_inventory = Inventory.active().filter(item=item).first().quantity
    future_deliveries = ScheduledDelivery.active().filter(
        purchase__item=item, delivery_date__gte=start_date
    )
    # 100 days
    future_supply = [0] * n_days
    demand_forecast = [0] * n_days

    for delivery in future_deliveries:
        day = (delivery.delivery_date - start_date).days
        if day > 0 and day < len(future_supply):
            future_supply[day] += delivery.quantity

    for day in range(n_days):
        day_of = start_date + timedelta(days=day)
        scaling_factor = compute_scaling_factor(
            past_period=dc.Period(
                demand_for_asset.start_date, demand_for_asset.end_date
            ),
            projection_period=dc.Period(day_of, day_of + timedelta(days=1)),
            demand_calculation_config=DemandCalculationConfig(),
        )
        import pdb

        pdb.set_trace()
        demand_forecast[day] += int(scaling_factor * demand_for_asset.demand)

    return generate_forecast(
        start_date, start_inventory, demand_forecast, future_supply
    )


def generate_forecast(start_date, start_inventory, demand_forecast, known_supply):
    # Create the linear solver with the GLOP backend.
    solver = pywraplp.Solver(
        "simple_lp_program", pywraplp.Solver.GLOP_LINEAR_PROGRAMMING
    )

    days = list(range(1, len(demand_forecast)))
    demand_vars = []
    supply_vars = []
    additional_supply_vars = []
    inventory_vars = []

    demand_vars.append(solver.NumVar(0, 0, "demand-d0"))
    supply_vars.append(solver.NumVar(0, 0, "supply-d0"))
    additional_supply_vars.append(solver.NumVar(0, 0, "add-supply-d0"))

    # initial demand is known
    inventory_vars.append(
        solver.NumVar(start_inventory, start_inventory, "inventory-d0")
    )

    # create variables for each day
    for day in days:
        # demand is given
        demand = demand_forecast[day - 1]
        demand_vars.append(solver.NumVar(demand, demand, "demand-d" + str(day)))

        # known supply is given
        supply = known_supply[day - 1]
        supply_vars.append(solver.NumVar(supply, supply, "supply-d" + str(day)))

        # additional supply needed every day
        additional_supply_vars.append(
            solver.NumVar(0, solver.infinity(), "add-supply-d" + str(day))
        )

        # inventory is known at d=0, and unknown in the future
        inventory_vars.append(
            solver.NumVar(0, solver.infinity(), "inventory-d" + str(day))
        )

    # Total Variables
    print("Number of variables =", solver.NumVariables())

    for day in days:
        # Create a linear constraint connecting the inventory changes.
        # inventory_(N-1) + supply_(N-1) + additional_supply_(N-1) - demand_(N) = inventory_(N)
        ct = solver.Constraint(0, 0, "Constraint-d" + str(day - 1) + "->d" + str(day))
        ct.SetCoefficient(inventory_vars[day - 1], 1)
        ct.SetCoefficient(supply_vars[day - 1], 1)
        ct.SetCoefficient(additional_supply_vars[day - 1], 1)
        ct.SetCoefficient(demand_vars[day], -1)
        ct.SetCoefficient(inventory_vars[day], -1)

    print("Number of constraints =", solver.NumConstraints())

    # Create the objective function to minimize total additional supplies.
    objective = solver.Objective()
    for day in days:
        objective.SetCoefficient(additional_supply_vars[day], 1)
    objective.SetMinimization()

    status = solver.Solve()
    import pdb

    pdb.set_trace()
    if status != pywraplp.Solver.OPTIMAL:
        return []

    forecast_result = []
    import pdb

    pdb.set_trace()
    for day in days:
        forecast_result.append(
            Forecast(
                date=(start_date + timedelta(days=day - 1)).strftime("%Y%m%d"),
                demand=demand_vars[day].solution_value(),
                existing_supply=supply_vars[day].solution_value(),
                additional_supply=additional_supply_vars[day].solution_value(),
                inventory=inventory_vars[day].solution_value(),
            )
        )

    return forecast_result
