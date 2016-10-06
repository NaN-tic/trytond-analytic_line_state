# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.analytic_line_state.tests.test_analytic_line_state import suite
except ImportError:
    from .test_analytic_line_state import suite

__all__ = ['suite']
