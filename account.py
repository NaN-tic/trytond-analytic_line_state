# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import logging
import time
from itertools import chain

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__all__ = ['Configuration', 'Account', 'Move', 'MoveLine']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'account.configuration'
    validate_analytic = fields.Boolean('Validate Analytic',
        help='If marked it will prevent to post a move to an account that '
        'has Pending Analytic accounts.')


class Account:
    __name__ = 'account.account'

    analytic_required = fields.Many2Many(
        'analytic_account.account-required-account.account', 'account',
        'analytic_account', 'Analytic Required', domain=[
            ('type', '=', 'root'),
            ('id', 'not in', Eval('analytic_forbidden')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('kind') == 'view',
            }, depends=['analytic_forbidden', 'analytic_optional', 'kind'])
    analytic_forbidden = fields.Many2Many(
        'analytic_account.account-forbidden-account.account', 'account',
        'analytic_account', 'Analytic Forbidden', domain=[
            ('type', '=', 'root'),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('kind') == 'view',
            }, depends=['analytic_required', 'analytic_optional', 'kind'])
    analytic_optional = fields.Many2Many(
        'analytic_account.account-optional-account.account', 'account',
        'analytic_account', 'Analytic Optional', domain=[
            ('type', '=', 'root'),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ], states={
            'invisible': Eval('kind') == 'view',
            }, depends=['analytic_required', 'analytic_forbidden', 'kind'])
    analytic_pending_accounts = fields.Function(
        fields.Many2Many('analytic_account.account', None, None,
            'Pending Accounts', states={
                'invisible': Eval('kind') == 'view',
                }, depends=['kind']),
        'on_change_with_analytic_pending_accounts')

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._error_messages.update({
                'analytic_account_required_forbidden': (
                    'The Account "%(account)s" has configured the next '
                    'Analytic Roots as Required and Forbidden at once: '
                    '%(roots)s.'),
                'analytic_account_required_optional': (
                    'The Account "%(account)s" has configured the next '
                    'Analytic Roots as Required and Optional at once: '
                    '%(roots)s.'),
                'analytic_account_forbidden_optional': (
                    'The Account "%(account)s" has configured the next '
                    'Analytic Roots as Forbidden and Optional at once: '
                    '%(roots)s.'),
                })

    @fields.depends('analytic_required', 'analytic_forbidden',
            'analytic_optional')
    def on_change_with_analytic_pending_accounts(self, name=None):
        AnalyticAccount = Pool().get('analytic_account.account')

        current_accounts = map(int, self.analytic_required)
        current_accounts += map(int, self.analytic_forbidden)
        current_accounts += map(int, self.analytic_optional)
        pending_accounts = AnalyticAccount.search([
                ('type', '=', 'root'),
                ('id', 'not in', current_accounts),
                ])
        return map(int, pending_accounts)

    def analytic_constraint(self, analytic_account):
        if analytic_account.root in self.analytic_required:
            return 'required'
        elif analytic_account.root in self.analytic_forbidden:
            return 'forbidden'
        elif analytic_account.root in self.analytic_optional:
            return 'optional'
        return 'undefined'

    @classmethod
    def validate(cls, accounts):
        super(Account, cls).validate(accounts)
        for account in accounts:
            account.check_analytic_accounts()

    def check_analytic_accounts(self):
        required = set(self.analytic_required)
        forbidden = set(self.analytic_forbidden)
        optional = set(self.analytic_optional)
        if required & forbidden:
            self.raise_user_error('analytic_account_required_forbidden', {
                    'account': self.rec_name,
                    'roots': ', '.join(a.rec_name
                        for a in (required & forbidden))
                    })
        if required & optional:
            self.raise_user_error('analytic_account_required_optional', {
                    'account': self.rec_name,
                    'roots': ', '.join(a.rec_name
                        for a in (required & optional))
                    })
        if forbidden & optional:
            self.raise_user_error('analytic_account_forbidden_optional', {
                    'account': self.rec_name,
                    'roots': ', '.join(a.rec_name
                        for a in (forbidden & optional))
                    })


class Move:
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._error_messages.update({
                'missing_analytic_lines': (
                    'The Account Move "%(move)s" can\'t be posted because it '
                    'doesn\'t have analytic lines for the next required '
                    'analytic hierachies: %(roots)s.'),
                'invalid_analytic_to_post_move': (
                    'The Account Move "%(move)s" can\'t be posted because the '
                    'Analytic Lines of hierachy "%(root)s" related to Move '
                    'Line "%(line)s" are not valid.'),
                })

    @classmethod
    @ModelView.button
    def post(cls, moves):
        super(Move, cls).post(moves)
        for move in moves:
            for line in move.lines:
                required_roots = list(line.account.analytic_required[:])
                if not line.analytic_lines and line.account.analytic_required:
                    cls.raise_user_error('missing_analytic_lines', {
                            'move': move.rec_name,
                            'roots': ', '.join(r.rec_name
                                for r in required_roots),
                            })

                for analytic_line in line.analytic_lines:
                    if analytic_line.account.root in required_roots:
                        required_roots.remove(analytic_line.account.root)
                    constraint = line.account.analytic_constraint(
                        analytic_line.account)
                    if (constraint == 'required' and
                            analytic_line.state != 'valid'):
                        cls.raise_user_error('invalid_analytic_to_post_move', {
                                'move': move.rec_name,
                                'line': line.rec_name,
                                'root': analytic_line.account.root.rec_name,
                                })
                if required_roots:
                    cls.raise_user_error('missing_analytic_lines', {
                            'move': move.rec_name,
                            'roots': ', '.join(r.rec_name
                                for r in required_roots),
                            })


class MoveLine:
    __name__ = 'account.move.line'

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        if not cls.analytic_lines.context:
            cls.analytic_lines.context = {}
        for name in ('debit', 'credit', 'journal', 'move', 'party',
                'description', 'move_description'):
            if not name in cls.analytic_lines.context:
                cls.analytic_lines.context[name] = Eval(name)
        if not 'date' in cls.analytic_lines.context:
            cls.analytic_lines.context['date'] = (
                Eval('_parent_move', {}).get('date')
                )
        cls._error_messages.update({
                'account_analytic_not_configured': (
                    'The Move Line "%(line)s" is related to the Account '
                    '"%(account)s" which is not configured for all Analytic '
                    'hierarchies.'),
                })

    @classmethod
    def validate(cls, lines):
        super(MoveLine, cls).validate(lines)
        for line in lines:
            line.check_account_analytic_configuration()

    def check_account_analytic_configuration(self):
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config.get_singleton()
        if config and config.validate_analytic:
            if self.account.analytic_pending_accounts:
                self.raise_user_error('account_analytic_not_configured', {
                        'line': self.rec_name,
                        'account': self.account.rec_name,
                        })

    @classmethod
    def validate_analytic_lines(cls, lines):
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')

        start_time = time.time()
        todraft, tovalid = [], []
        for line in lines:
            analytic_lines_by_root = {}
            for analytic_line in line.analytic_lines:
                analytic_lines_by_root.setdefault(analytic_line.account.root,
                    []).append(analytic_line)

            line_balance = line.debit - line.credit
            for analytic_lines in analytic_lines_by_root.values():
                balance = sum((al.debit - al.credit) for al in analytic_lines)
                if balance == line_balance:
                    tovalid += [al for al in analytic_lines
                        if al.state != 'valid']
                else:
                    todraft += [al for al in analytic_lines
                        if al.state != 'draft']
        if todraft:
            AnalyticLine.write(todraft, {
                    'state': 'draft',
                    })
        if tovalid:
            AnalyticLine.write(tovalid, {
                    'state': 'valid',
                    })
        logging.getLogger(cls.__name__).debug(
            "validate_analytic_lines(): %s seconds"
            % (time.time() - start_time))
        return todraft + tovalid

    @classmethod
    def create(cls, vlist):
        lines = super(MoveLine, cls).create(vlist)
        cls.validate_analytic_lines(lines)
        return lines

    @classmethod
    def write(cls, *args):
        super(MoveLine, cls).write(*args)
        lines = list(chain(*args[::2]))
        cls.validate_analytic_lines(lines)

    @classmethod
    def delete(cls, lines):
        AnalyticLine = Pool().get('analytic_account.line')
        todraft_lines = [al for line in lines for al in line.analytic_lines]
        super(MoveLine, cls).delete(lines)
        AnalyticLine.write(todraft_lines, {
                'state': 'draft',
                })
