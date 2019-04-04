# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.exceptions import UserError
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear


class TestCase(ModuleTestCase):
    '''
    Test module.
    '''
    module = 'analytic_line_state'

    @with_transaction()
    def test0010analytic_account_chart(self):
        'Test creation of minimal analytic chart of accounts'
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        Party = pool.get('party.party')
        transaction = Transaction()

        # Create Company
        party = Party(name='Party')
        party.save()
        company = create_company()
        with set_company(company):
            root, = AnalyticAccount.create([{
                        'name': 'Root',
                        'type': 'root',
                        },
                    ])
            AnalyticAccount.create([{
                        'name': 'Projects',
                        'root': root.id,
                        'parent': root.id,
                        'type': 'view',
                        'childs': [
                            ('create', [{
                                        'name': 'Project 1',
                                        'code': 'P1',
                                        'root': root.id,
                                        'type': 'normal',
                                        }, {
                                        'name': 'Project 2',
                                        'code': 'P2',
                                        'root': root.id,
                                        'type': 'normal',
                                        },
                                    ]),
                            ],
                        },
                    ])

            transaction.commit()

    def configure_analytic_accounts(self):
        pool = Pool()
        Account = pool.get('account.account')
        AnalyticAccount = pool.get('analytic_account.account')
        revenue_expense = Account.search([
                'OR',('type.expense', '=', True),
                ('type.revenue', '=', True)
                ])
        receivable_payable = Account.search([
                'OR', ('type.payable', '=', True),
                ('type.receivable', '=', True)
                ])
        other = Account.search([
                ('type','!=', None),
                ('type.revenue', '=', False),
                ('type.expense', '=', False),
                ('type.payable', '=', False),
                ('type.receivable', '=', False)
                ])
        roots = AnalyticAccount.search([
                ('type', '=', 'root')
                ])
        AnalyticAccount.write(roots, {
                    'analytic_required': [
                        ('add', [x.id for x in revenue_expense]),
                        ],
                    'analytic_forbidden': [
                        ('add', [x.id for x in receivable_payable]),
                        ],
                    'analytic_optional': [
                        ('add', [x.id for x in other]),
                        ],
                })
        # Check all General accounts are configured
        for root in roots:
            self.assertEqual(len(root.analytic_pending_accounts), 0)

    @with_transaction()
    def test0020account_constraints(self):
        'Test account configuration constraints'
        pool = Pool()
        Account = pool.get('account.account')
        AnalyticAccount = pool.get('analytic_account.account')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Party = pool.get('party.party')
        Company = pool.get('company.company')

        party, = Party.search([('name', '=', 'Party')])
        company, = Company.search([])
        with set_company(company):
            root, = AnalyticAccount.create([{
                        'type': 'root',
                        'name': 'Root',
                        }])
            analytic_account, = AnalyticAccount.create([{
                        'type': 'normal',
                        'name': 'Analytic Account',
                        'parent': root.id,
                        'root': root.id,
                        }])

            # Create Chart and Fiscalyear
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            fiscalyear.create_period([fiscalyear])
            period = fiscalyear.periods[0]

            self.configure_analytic_accounts()

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = Journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True)
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True)
                    ])
            expense, = Account.search([
                    ('type.expense', '=', True)
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True)
                    ])
            project1, = AnalyticAccount.search([
                    ('code', '=', 'P1'),
                    ])
            project2, = AnalyticAccount.search([
                    ('code', '=', 'P2'),
                    ])
            # root = project1.root

            # # Can add account in required and forbidden
            # with self.assertRaises(UserError):
            #   root.analytic_required = root.analytic_required + (receivable,)
            #    root.save()
            # # Can add account in required and optional
            # with self.assertRaises(UserError):
            #    root.analytic_optional = root.analytic_optional + (expense,)
            #    root.save()
            # # Can add account in forbidden and optional
            # with self.assertRaises(UserError):
            #   root.analytic_optional = root.analytic_optional + (receivable,)
            #    root.save()

            # # Can create move with analytic in analytic required account and
            # without analytic in forbidden account
            analytic_lines_value = [('create', [{
                            'debit': Decimal(0),
                            'credit': Decimal(30000),
                            'account': project1.id,
                            'date': period.start_date,
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
                                'party': party.id,
                                'account': receivable.id,
                                'debit': Decimal(30000),
                                }]),
                    ],
                }
            valid_move, = Move.create([valid_move_vals])
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
                            'party': party.id,
                            'account': receivable.id,
                            'debit': Decimal(30000),
                            }]),
                ]
            missing_analytic_move = Move.create([missing_analytic_vals])
            with self.assertRaises(UserError):
                Move.post(missing_analytic_move)

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
                Move.create([unexpected_analytic_vals])

    @with_transaction()
    def test0030analytic_line_state(self):
        'Test of analytic line workflow'
        pool = Pool()
        Account = pool.get('account.account')
        AnalyticAccount = pool.get('analytic_account.account')
        AnalyticLine = pool.get('analytic_account.line')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Party = pool.get('party.party')
        Company = pool.get('company.company')

        party, = Party.search([('name', '=', 'Party')])
        company, = Company.search([])
        with set_company(company):

            # Create Chart and Fiscalyear
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            fiscalyear.create_period([fiscalyear])
            period = fiscalyear.periods[0]

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            journal_expense, = Journal.search([
                    ('code', '=', 'EXP'),
                    ])
            revenue, = Account.search([
                    ('type.expense', '=', True),
                    ])
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            expense, = Account.search([
                    ('type.expense', '=', True),
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True),
                    ])
            project1, = AnalyticAccount.search([
                    ('code', '=', 'P1'),
                    ])
            project2, = AnalyticAccount.search([
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
                                                    'debit': Decimal(0),
                                                    'credit': Decimal(30000),
                                                    'date': today,
                                                    'account': project1.id,
                                                    }]),
                                        ],
                                    }, {
                                    'party': party.id,
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
                                    'party': party.id,
                                    'account': payable.id,
                                    'credit': Decimal(1100),
                                    }]),
                        ],
                    },
                ]
            valid_move, draft_move = Move.create(vlist)

            # Check the Analytic lines of the valid move are in 'valid' state
            self.assertTrue(all(al.state == 'valid'
                    for ml in valid_move.lines for al in ml.analytic_lines))
            # Can post the move
            Move.post([valid_move])
            self.assertEqual(valid_move.state, 'posted')

            # Create some analytic lines on draft move and check how their
            # state change
            expense_move_line = [l for l in draft_move.lines
                if l.account.type.expense][0]
            line1, = AnalyticLine.create([{
                        'credit': Decimal(0),
                        'debit': Decimal(600),
                        'account': project1.id,
                        'move_line': expense_move_line.id,
                        'date': today - relativedelta(days=15),
                        }])
            self.assertEqual(line1.state, 'draft')

            # # Can't post move because analytic is not valid
            # with self.assertRaises(UserError):
            #    Move.post([draft_move])

            line2, = AnalyticLine.create([{
                        'credit': Decimal(0),
                        'debit': Decimal(500),
                        'account': project1.id,
                        'date': today - relativedelta(days=10),
                        }])
            self.assertEqual(line1.state, 'draft')

            line2.move_line = expense_move_line
            line2.save()
            self.assertEqual(line2.state, 'valid')
            self.assertEqual(line1.state, 'valid')

            # Can post the move
            Move.post([draft_move])
            self.assertEqual(draft_move.state, 'posted')

    @with_transaction()
    def test0040account_configuration(self):
        'Test account configuration configuration'
        pool = Pool()
        Account = pool.get('account.account')
        AnalyticAccount = pool.get('analytic_account.account')
        Configuration = pool.get('account.configuration')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Party = pool.get('party.party')
        Company = pool.get('company.company')

        party, = Party.search([('name', '=', 'Party')])
        company, = Company.search([])
        with set_company(company):
            root, = AnalyticAccount.search([
                    ('type', '=', 'root')
                    ])

            # Create Chart and Fiscalyear
            create_chart(company)
            fiscalyear = get_fiscalyear(company)
            fiscalyear.save()
            fiscalyear.create_period([fiscalyear])
            period = fiscalyear.periods[0]

            self.assertGreater(len(root.analytic_pending_accounts), 0)

            journal_revenue, = Journal.search([
                    ('code', '=', 'REV'),
                    ])
            other, = Account.search([
                    ('type.revenue', '=', False),
                    ('type.receivable', '=', False),
                    ('type.expense', '=', False),
                    ('type.payable', '=', False),
                    ], limit=1)
            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            project1, = AnalyticAccount.search([
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
                                                    'debit': Decimal(0),
                                                    'credit': Decimal(30000),
                                                    'account': project1.id,
                                                    'date': period.start_date,
                                                    }]),
                                        ],
                                    }, {
                                    'party': party.id,
                                    'account': receivable.id,
                                    'debit': Decimal(30000),
                                    }]),
                        ],
                    }]
            # Doesnt raise any error
            move = Move.create(values)
            Move.post(move)

            Configuration.write([], {
                    'validate_analytic': True,
                    })
            with self.assertRaises(UserError):
                move = Move.create(values)
                Move.post(move)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
