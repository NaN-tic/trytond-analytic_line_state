# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool

import account
import analytic


def register():
    Pool.register(
        account.Configuration,
        analytic.AnalyticAccount,
        analytic.AnalyticAccountAccountRequired,
        analytic.AnalyticAccountAccountForbidden,
        analytic.AnalyticAccountAccountOptional,
        analytic.AnalyticLine,
        account.Account,
        account.Move,
        account.MoveLine,
        analytic.OpenChartAccountStart,
        module='analytic_line_state', type_='model')
    Pool.register(
        analytic.OpenChartAccount,
        module='analytic_line_state', type_='wizard')
