# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import account
from . import analytic
from . import invoice

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
        invoice.InvoiceLine,
        depends=['account_invoice'],
        module='analytic_line_state', type_='model')
    Pool.register(
        analytic.OpenChartAccount,
        module='analytic_line_state', type_='wizard')
