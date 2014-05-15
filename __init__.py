# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .account import *
from .analytic import *


def register():
    Pool.register(
        Configuration,
        AnalyticAccount,
        AnalyticAccountAccountRequired,
        AnalyticAccountAccountForbidden,
        AnalyticAccountAccountOptional,
        AnalyticLine,
        Account,
        Move,
        MoveLine,
        OpenChartAccountStart,
        module='analytic_line_state', type_='model')
    Pool.register(
        OpenChartAccount,
        module='analytic_line_state', type_='wizard')
