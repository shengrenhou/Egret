#  ___________________________________________________________________________
#
#  EGRET: Electrical Grid Research and Engineering Tools
#  Copyright 2019 National Technology & Engineering Solutions of Sandia, LLC
#  (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
#  Government retains certain rights in this software.
#  This software is distributed under the Revised BSD License.
#  ___________________________________________________________________________


## system variables and constraints
from pyomo.environ import *
from pyomo.core.expr.numeric_expr import LinearExpression
import math

from .uc_utils import add_model_attr, is_var, linear_summation
from .reserve_vars import check_reserve_requirement
component_name = 'reserve_requirement'

def _add_reserve_shortfall(model, fixed=False):
    if fixed:
        model.ReserveShortfall = Var(model.TimePeriods, bounds=(0.,0.))
    else:
        # the reserve shortfall can't be more than the reserve requirement in any given time period.
        model.ReserveShortfall = Var(model.TimePeriods, bounds=lambda m,t:(0., m.ReserveRequirement[t]))

@add_model_attr(component_name, requires = {'data_loader': None,
                                            'reserve_vars': None,
                                            'non_dispatchable_vars': None,
                                            'storage_service': None,
                                            })
def CA_reserve_constraints(model):
    '''
    This is the reserve requirement with slacks given by equation (3) in

    Carrion, M. and Arroyo, J. (2006) A Computationally Efficient Mixed-Integer
    Liner Formulation for the Thermal Unit Commitment Problem. IEEE Transactions
    on Power Systems, Vol. 21, No. 3, Aug 2006.
    '''

    if not check_reserve_requirement(model):
        _add_reserve_shortfall(model, fixed=True)
        return
    _add_reserve_shortfall(model)

    # ensure there is sufficient maximal power output available to meet both the
    # demand and the spinning reserve requirements in each time period.
    # encodes Constraint 3 in Carrion and Arroyo.
    
    # IMPT: In contrast to power balance, reserves are (1) not per-bus and (2) expressed in terms of 
    #       maximum power available, and not actual power generated.
    if is_var(model.MaximumPowerAvailable) and is_var(model.NondispatchablePowerUsed) and \
            is_var(model.PowerOutputStorage) and is_var(model.PowerInputStorage) and \
            is_var(model.LoadGenerateMismatch):
        linear_expr = LinearExpression
    else:
        linear_expr = linear_summation
    
    def enforce_reserve_requirements_rule(m, t):
        linear_vars = list(m.MaximumPowerAvailable[g, t] for g in m.ThermalGenerators) \
                 + list(m.NondispatchablePowerUsed[n,t] for n in m.AllNondispatchableGenerators) \
                 + list(m.PowerOutputStorage[s,t] for s in m.Storage) \
                 + list(m.LoadGenerateMismatch[b,t] for b in m.Buses)
        linear_vars.append(m.ReserveShortfall[t])
        linear_coefs = [1.]*len(linear_vars)

        neg_vars = list(m.PowerInputStorage[s,t] for s in m.Storage)
        neg_coefs = [-1.]*len(neg_vars)

        linear_vars.extend(neg_vars)
        linear_coefs.extend(neg_coefs)

        return (m.TotalDemand[t]+m.ReserveRequirement[t],
                linear_expr(linear_vars=linear_vars, linear_coefs=linear_coefs),
                None)
    
    model.EnforceReserveRequirements = Constraint(model.TimePeriods, rule=enforce_reserve_requirements_rule)

    return
## end carrion_reserve_constraints


## helper for reserve pricing problem
def _MLR_reserve_constraint(model):

    def enforce_reserve_requirements_rule(m, t):
        return sum(m.ReserveProvided[g, t] for g in m.ThermalGenerators) \
                 + m.ReserveShortfall[t] \
                 >= \
                 m.ReserveRequirement[t]
    
    model.EnforceReserveRequirements = Constraint(model.TimePeriods, rule=enforce_reserve_requirements_rule)



@add_model_attr(component_name, requires = {'data_loader': None,
                                            'reserve_vars': None,
                                            })
def MLR_reserve_constraints(model):
    '''
    This is the reserve requirement with slacks given by equation (5) in
    
    G. Morales-Espana, J. M. Latorre, and A. Ramos. Tight and compact MILP
    formulation for the thermal unit commitment problem. IEEE Transactions on
    Power Systems, 28(4):4897–4908, 2013.
    '''

    _add_reserve_shortfall(model, fixed=True)

    if not check_reserve_requirement(model):
        _add_reserve_shortfall(model, fixed=True)
        return

    _add_reserve_shortfall(model)
    # ensure there is sufficient maximal power output available to meet both the
    # demand and the spinning reserve requirements in each time period.
    # encodes Constraint 3 in Carrion and Arroyo.
    
    # IMPT: In contrast to power balance, reserves are (1) not per-bus and (2) expressed in terms of 
    #       maximum power available, and not actual power generated.
    _MLR_reserve_constraint(model)

    return
## end carrion_reserve_constraints
