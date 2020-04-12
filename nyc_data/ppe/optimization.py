from ortools.linear_solver import pywraplp
from datetime import datetime
from datetime import timedelta
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


def generate_forecast(start_date,
                      start_inventory,
                      demand_forecast,
                      known_supply):

    # Create the linear solver with the GLOP backend.
    solver = pywraplp.Solver('simple_lp_program',
                             pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)

    days = list(range(1, len(demand_forecast)))
    demand_vars = []
    supply_vars = []
    additional_supply_vars = []
    inventory_vars = []

    demand_vars.append(solver.NumVar(0, 0, 'demand-d0'))
    supply_vars.append(solver.NumVar(0, 0, 'supply-d0'))
    additional_supply_vars.append(solver.NumVar(0, 0, 'add-supply-d0'))

    # initial demand is known
    inventory_vars.append(solver.NumVar(start_inventory, start_inventory,
                                        'inventory-d0'))

    # create variables for each day
    for day in days:
        # demand is given
        demand = demand_forecast[day-1]
        demand_vars.append(solver.NumVar(demand, demand, 'demand-d'+str(day)))

        # known supply is given
        supply = known_supply[day-1]
        supply_vars.append(solver.NumVar(supply, supply, 'supply-d'+str(day)))

        # additional supply needed every day
        additional_supply_vars.append(solver.NumVar(0, solver.infinity(), 'add-supply-d'+str(day)))

        # inventory is known at d=0, and unknown in the future
        inventory_vars.append(solver.NumVar(0, solver.infinity(), 'inventory-d'+str(day)))

    # Total Variables
    print('Number of variables =', solver.NumVariables())

    for day in days:
        # Create a linear constraint connecting the inventory changes.
        # inventory_(N-1) + supply_(N-1) + additional_supply_(N-1) - demand_(N) = inventory_(N)
        ct = solver.Constraint(0, 0, 'Constraint-d' + str(day-1) + '->d' + str(day))
        ct.SetCoefficient(inventory_vars[day-1], 1)
        ct.SetCoefficient(supply_vars[day-1], 1)
        ct.SetCoefficient(additional_supply_vars[day-1], 1)
        ct.SetCoefficient(demand_vars[day], -1)
        ct.SetCoefficient(inventory_vars[day], -1)

    print('Number of constraints =', solver.NumConstraints())

    # Create the objective function to minimize total additional supplies.
    objective = solver.Objective()
    for day in days:
        objective.SetCoefficient(additional_supply_vars[day], 1)
    objective.SetMinimization()

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        return []

    forecast_result = []
    for day in days:
        forecast_result.append(Forecast(date=(start_date + timedelta(days=day-1)).strftime('%Y%m%d'),
                                        demand=demand_vars[day].solution_value(),
                                        existing_supply=supply_vars[day].solution_value(),
                                        additional_supply=additional_supply_vars[day].solution_value(),
                                        inventory=inventory_vars[day].solution_value()))

    return forecast_result
