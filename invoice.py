# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

__all__ = ['InvoiceLine']


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        # analytic_invoice add analytic accounts when is supplier invoice (in)
        # See issue5909
        # In case the invoice line has analytic accounts and customer invoice,
        # copy analytic lines to move lines.
        if type_ == 'out' and self.analytic_accounts:
            date = self.invoice.accounting_date or self.invoice.invoice_date
            for line in lines:
                analytic_lines = []
                for entry in self.analytic_accounts:
                    analytic_lines.extend(
                        entry.get_analytic_lines(line, date))
                line.analytic_lines = analytic_lines
        return lines
