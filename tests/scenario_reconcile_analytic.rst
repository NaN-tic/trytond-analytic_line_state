===================================
Analytic Account Reconcile Scenario
===================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertTrue

Activate modules::

    >>> config = activate_modules('analytic_line_state')

    >>> Reconciliation = Model.get('account.move.reconciliation')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> Journal = Model.get('account.journal')
    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()
    >>> analytic_account2 = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic 2')
    >>> analytic_account2.save()

Create analytic rules::

    >>> AnalyticRule = Model.get('analytic_account.rule')
    >>> rule1 = AnalyticRule(company=company, account=expense)
    >>> entry, = rule1.analytic_accounts
    >>> entry.account = analytic_account
    >>> rule1.save()
    >>> rule2 = AnalyticRule(company=company, account=revenue)
    >>> entry, = rule2.analytic_accounts
    >>> entry.account = analytic_account2
    >>> rule2.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Move analytic accounts for writeoff reconciliation::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.credit = line.credit
    >>> analytic_line.account = analytic_account
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.click('post')
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('0.00')
    >>> reconcile1, = [l for l in move.lines if l.account == receivable]

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.credit = Decimal(65)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(65)
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.credit = line.credit
    >>> analytic_line.account = analytic_account
    >>> line.party = customer
    >>> move.click('post')
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('65.00')
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]

Create a write-off payment method::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find(
    ...     [('sequence_type.name', '=', "Account Journal")], limit=1)
    >>> journal_writeoff = Journal(name='Write-Off', type='write-off',
    ...     sequence=sequence_journal)
    >>> journal_writeoff.save()
    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> writeoff_method = WriteOff()
    >>> writeoff_method.name = 'Write Off'
    >>> writeoff_method.journal = journal_writeoff
    >>> writeoff_method.debit_account = expense
    >>> writeoff_method.credit_account = expense
    >>> writeoff_method.save()

Reconcile Lines with write-off::

    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.form_state
    'writeoff'
    >>> reconcile_lines.form.writeoff = writeoff_method
    >>> reconcile_lines.execute('reconcile')
    >>> reconcile1.reload()
    >>> reconcile2.reload()
    >>> assertEqual(reconcile1.reconciliation, reconcile2.reconciliation)
    >>> assertTrue(reconcile1.reconciliation)
    >>> len(reconcile1.reconciliation.lines)
    3
    >>> writeoff_line1, = [l for l in reconcile1.reconciliation.lines
    ...     if l.credit == Decimal(107)]
    >>> writeoff_line2, = [l for l in writeoff_line1.move.lines
    ...     if l != writeoff_line1]
    >>> assertEqual(writeoff_line2.account, expense)
    >>> writeoff_line2.debit == Decimal('107')
    True
    >>> assertEqual(len(writeoff_line2.analytic_lines), 1)
    >>> assertEqual(writeoff_line2.analytic_lines[0].account, analytic_account)
