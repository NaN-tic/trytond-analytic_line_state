#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
import unittest
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.exceptions import UserError
from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    test_view, test_depends)
from trytond.transaction import Transaction


class TestCase(unittest.TestCase):
    '''
    Test module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('analytic_line_state')
        self.account = POOL.get('account.account')
        self.analytic_account = POOL.get('analytic_account.account')
        self.analytic_line = POOL.get('analytic_account.line')
        self.company = POOL.get('company.company')
        self.configuration = POOL.get('account.configuration')
        self.fiscalyear = POOL.get('account.fiscalyear')
        self.journal = POOL.get('account.journal')
        self.move = POOL.get('account.move')
        self.sequence = POOL.get('ir.sequence')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('analytic_line_state')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010analytic_account_chart(self):
        'Test creation of minimal analytic chart of accounts'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency

            root, = self.analytic_account.create([{
                        'name': 'Root',
                        'company': company.id,
                        'currency': currency.id,
                        'type': 'root',
                        },
                    ])
            self.analytic_account.create([{
                        'name': 'Projects',
                        'company': company.id,
                        'currency': currency.id,
                        'root': root.id,
                        'parent': root.id,
                        'type': 'view',
                        'childs': [
                            ('create', [{
                                        'name': 'Project 1',
                                        'code': 'P1',
                                        'company': company.id,
                                        'currency': currency.id,
                                        'root': root.id,
                                        'type': 'normal',
                                        }, {
                                        'name': 'Project 2',
                                        'code': 'P2',
                                        'company': company.id,
                                        'currency': currency.id,
                                        'root': root.id,
                                        'type': 'normal',
                                        },
                                    ]),
                            ],
                        },
                    ])

            transaction.cursor.commit()

    def configure_analytic_accounts(self):
        revenue_expense = self.account.search([
                ('kind', 'in', ('revenue', 'expense')),
                ])
        receivable_payable = self.account.search([
                ('kind', 'in', ('receivable', 'payable')),
                ])
        other = self.account.search([
                ('kind', '=', 'other'),
                ])
        roots = self.analytic_account.search([
                ('type', '=', 'root')
                ])
        self.analytic_account.write(roots, {
                    'analytic_required': [
                        ('add', map(int, revenue_expense)),
                        ],
                    'analytic_forbidden': [
                        ('add', map(int, receivable_payable)),
                        ],
                    'analytic_optional': [
                        ('add', [a.id for a in other]),
                        ],
                })
        # Check all General accounts are configured
        for root in roots:
            self.assertEqual(len(root.analytic_pending_accounts), 0)

    def test0020account_constraints(self):
        'Test account configuration constraints'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.configure_analytic_accounts()
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            fiscalyear, = self.fiscalyear.search([])
            period = fiscalyear.periods[0]
            journal_revenue, = self.journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = self.journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = self.account.search([
                    ('kind', '=', 'revenue'),
                    ])
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ])
            expense, = self.account.search([
                    ('kind', '=', 'expense'),
                    ])
            payable, = self.account.search([
                    ('kind', '=', 'payable'),
                    ])
            project1, = self.analytic_account.search([
                    ('code', '=', 'P1'),
                    ])
            project2, = self.analytic_account.search([
                    ('code', '=', 'P2'),
                    ])
            #root = project1.root

            # Can add account in required and forbidden
            #with self.assertRaises(UserError):
            #   root.analytic_required = root.analytic_required + (receivable,)
            #    root.save()
            ## Can add account in required and optional
            #with self.assertRaises(UserError):
            #    root.analytic_optional = root.analytic_optional + (expense,)
            #    root.save()
            ## Can add account in forbidden and optional
            #with self.assertRaises(UserError):
            #   root.analytic_optional = root.analytic_optional + (receivable,)
            #    root.save()

            # Can create move with analytic in analytic required account and
            # without analytic in forbidden account
            analytic_lines_value = [('create', [{
                            'name': 'Contribution',
                            'debit': Decimal(0),
                            'credit': Decimal(30000),
                            'currency': currency.id,
                            'account': project1.id,
                            'journal': journal_revenue.id,
                            }]),
                ]
            valid_move_vals = {
                'period': period.id,
                'journal': journal_revenue.id,
                'date': period.start_date,
                'lines': [
                    ('create', [{
                                'account': revenue.id,
                                'credit': Decimal(30000),
                                'analytic_lines': analytic_lines_value,
                                }, {
                                'account': receivable.id,
                                'debit': Decimal(30000),
                                }]),
                    ],
                }
            valid_move, = self.move.create([valid_move_vals])
            self.assertTrue(all(al.state == 'valid'
                    for ml in valid_move.lines for al in ml.analytic_lines))

            # Can not post move without analytic in analytic required account
            missing_analytic_vals = valid_move_vals.copy()
            missing_analytic_vals['lines'] = [
                ('create', [{
                            'account': revenue.id,
                            'credit': Decimal(30000),
                            'analytic_lines': [],
                            }, {
                            'account': receivable.id,
                            'debit': Decimal(30000),
                            }]),
                ]
            missing_analytic_move = self.move.create([missing_analytic_vals])
            with self.assertRaises(UserError):
                self.move.post(missing_analytic_move)

            # Can not create move with analytic in analytic forbidden account
            unexpected_analytic_vals = valid_move_vals.copy()
            unexpected_analytic_vals['lines'] = [
                ('create', [
                    valid_move_vals['lines'][0][1][0], {
                        'account': receivable.id,
                        'debit': Decimal(30000),
                        'analytic_lines': analytic_lines_value,
                        }]),
                ]
            with self.assertRaises(UserError):
                self.move.create([unexpected_analytic_vals])

    def test0030analytic_line_state(self):
        'Test of analytic line workflow'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.configure_analytic_accounts()
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            fiscalyear, = self.fiscalyear.search([])
            period = fiscalyear.periods[0]
            journal_revenue, = self.journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = self.journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = self.account.search([
                    ('kind', '=', 'revenue'),
                    ])
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ])
            expense, = self.account.search([
                    ('kind', '=', 'expense'),
                    ])
            payable, = self.account.search([
                    ('kind', '=', 'payable'),
                    ])
            project1, = self.analytic_account.search([
                    ('code', '=', 'P1'),
                    ])
            project2, = self.analytic_account.search([
                    ('code', '=', 'P2'),
                    ])
            today = datetime.date.today()

            # Create some moves
            vlist = [{
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': revenue.id,
                                    'credit': Decimal(30000),
                                    'analytic_lines': [
                                        ('create', [{
                                                    'name': 'Contribution',
                                                    'debit': Decimal(0),
                                                    'credit': Decimal(30000),
                                                    'currency': currency.id,
                                                    'account': project1.id,
                                                    'journal':
                                                        journal_revenue.id,
                                                    }]),
                                        ],
                                    }, {
                                    'account': receivable.id,
                                    'debit': Decimal(30000),
                                    }]),
                        ],
                    }, {
                    'period': period.id,
                    'journal': journal_expense.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': expense.id,
                                    'debit': Decimal(1100),
                                    }, {
                                    'account': payable.id,
                                    'credit': Decimal(1100),
                                    }]),
                        ],
                    },
                ]
            valid_move, draft_move = self.move.create(vlist)

            # Check the Analytic lines of the valid move are in 'valid' state
            self.assertTrue(all(al.state == 'valid'
                    for ml in valid_move.lines for al in ml.analytic_lines))
            # Can post the move
            self.move.post([valid_move])
            self.assertEqual(valid_move.state, 'posted')

            # Create some analytic lines on draft move and check how their
            # state change
            expense_move_line = [l for l in draft_move.lines
                if l.account.kind == 'expense'][0]
            line1, = self.analytic_line.create([{
                        'name': 'Materials purchase',
                        'debit': Decimal(600),
                        'currency': currency.id,
                        'account': project1.id,
                        'move_line': expense_move_line.id,
                        'journal': journal_expense.id,
                        'date': today - relativedelta(days=15),
                        }])
            self.assertEqual(line1.state, 'draft')

            ## Can't post move because analytic is not valid
            #with self.assertRaises(UserError):
            #    self.move.post([draft_move])

            line2, = self.analytic_line.create([{
                        'name': 'Salaries',
                        'debit': Decimal(500),
                        'currency': currency.id,
                        'account': project1.id,
                        'journal': journal_expense.id,
                        'date': today - relativedelta(days=10),
                        }])
            self.assertEqual(line1.state, 'draft')

            line2.move_line = expense_move_line
            line2.save()
            self.assertEqual(line2.state, 'valid')
            self.assertEqual(line1.state, 'valid')

            # Can post the move
            self.move.post([draft_move])
            self.assertEqual(draft_move.state, 'posted')

    def test0030account_configuration(self):
        'Test account configuration configuration'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            root, = self.analytic_account.search([
                    ('type', '=', 'root')
                    ])
            self.assertGreater(len(root.analytic_pending_accounts), 0)

            fiscalyear, = self.fiscalyear.search([])
            period = fiscalyear.periods[0]
            journal_revenue, = self.journal.search([
                    ('code', '=', 'REV'),
                    ])
            other, = self.account.search([
                    ('kind', '=', 'other'),
                    ], limit=1)
            receivable, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ])
            project1, = self.analytic_account.search([
                    ('code', '=', 'P1'),
                    ])

            values = [{
                    'period': period.id,
                    'journal': journal_revenue.id,
                    'date': period.start_date,
                    'lines': [
                        ('create', [{
                                    'account': other.id,
                                    'credit': Decimal(30000),
                                    'analytic_lines': [
                                        ('create', [{
                                                    'name': 'Contribution',
                                                    'debit': Decimal(0),
                                                    'credit': Decimal(30000),
                                                    'currency': currency.id,
                                                    'account': project1.id,
                                                    'journal':
                                                        journal_revenue.id,
                                                    }]),
                                        ],
                                    }, {
                                    'account': receivable.id,
                                    'debit': Decimal(30000),
                                    }]),
                        ],
                    }]
            #Doesnt raise any error
            move = self.move.create(values)
            self.move.post(move)

            self.configuration.write([], {
                    'validate_analytic': True,
                    })
            with self.assertRaises(UserError):
                move = self.move.create(values)
                self.move.post(move)


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    from trytond.modules.account.tests import test_account
    exclude_tests = ('test0005views', 'test0006depends',
        'test0020company_recursion', 'test0040user',
        'test0020mon_grouping', 'test0040rate_unicity',
        'test0060compute_nonfinite', 'test0070compute_nonfinite_worounding',
        'test0080compute_same', 'test0090compute_zeroamount',
        'test0100compute_zerorate', 'test0110compute_missingrate',
        'test0120compute_bothmissingrate', 'test0130delete_cascade',
        'scenario_account_reconciliation_rst')
    for test in test_company.suite():
        if test not in suite and test.id().split('.')[-1] not in exclude_tests:
            suite.addTest(test)
    for test in test_account.suite():
        if test not in suite and test.id().split('.')[-1] not in exclude_tests:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
