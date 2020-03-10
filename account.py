# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from itertools import chain

from trytond.model import ModelView, fields, dualmethod
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Configuration', 'Account', 'Move', 'MoveLine']


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    validate_analytic = fields.Boolean('Validate Analytic',
        help='If marked it will prevent to post a move to an account that '
        'has Pending Analytic accounts.')

class Account(metaclass=PoolMeta):
    __name__ = 'account.account'

    analytic_required = fields.Many2Many(
        'analytic_account.account-required-account.account', 'account',
        'analytic_account', 'Analytic Required', domain=[
            ('type', '=', 'root'),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible':~Bool(Eval('type')),
            },
        depends=['company', 'analytic_forbidden', 'analytic_optional', 'type'])
    analytic_forbidden = fields.Many2Many(
        'analytic_account.account-forbidden-account.account', 'account',
        'analytic_account', 'Analytic Forbidden', domain=[
            ('type', '=', 'root'),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible':~Bool(Eval('type')),
            },
        depends=['company', 'analytic_required', 'analytic_optional', 'type'])
    analytic_optional = fields.Many2Many(
        'analytic_account.account-optional-account.account', 'account',
        'analytic_account', 'Analytic Optional', domain=[
            ('type', '=', 'root'),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ], states={
            'invisible':~Bool(Eval('type')),
            },
        depends=['company', 'analytic_required', 'analytic_forbidden', 'type'])
    analytic_pending_accounts = fields.Function(
        fields.Many2Many('analytic_account.account', None, None,
            'Pending Accounts', states={
                'invisible':~Bool(Eval('type')),
                }, depends=['type']),
        'on_change_with_analytic_pending_accounts')


    @fields.depends('analytic_required', 'analytic_forbidden',
            'analytic_optional', 'company')
    def on_change_with_analytic_pending_accounts(self, name=None):
        AnalyticAccount = Pool().get('analytic_account.account')

        current_accounts = [x.id for x in self.analytic_required]
        current_accounts += [x.id for x in self.analytic_forbidden]
        current_accounts += [x.id for x in self.analytic_optional]
        pending_accounts = AnalyticAccount.search([
                ('type', '=', 'root'),
                ('company', '=', self.company),
                ('id', 'not in', current_accounts),
                ])
        return [x.id for x in pending_accounts]

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
            raise UserError(gettext(
                'analytic_line_state.analytic_account_required_forbidden',
                    account=self.rec_name,
                    roots=', '.join(a.rec_name
                        for a in (required & forbidden))
                    ))
        if required & optional:
            raise UserError(gettext(
                'analytic_line_state.analytic_account_required_optional',
                    account=self.rec_name,
                    roots=', '.join(a.rec_name
                        for a in (required & optional))
                    ))
        if forbidden & optional:
            raise UserError(gettext(
                'analytic_line_state.analytic_account_forbidden_optional',
                    account=self.rec_name,
                    roots=', '.join(a.rec_name
                        for a in (forbidden & optional))
                    ))


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    @ModelView.button
    def post(cls, moves):
        super(Move, cls).post(moves)
        for move in moves:
            origin = ''
            origin_model = ''
            if move.origin:
                origin = move.origin.rec_name
                origin_model = move.origin.__names__().get('model')
            if move.period.type == 'adjustment':
                continue
            for line in move.lines:
                required_roots = list(line.account.analytic_required[:])
                if not line.analytic_lines and line.account.analytic_required:
                    raise UserError(gettext(
                        'analytic_line_state.missing_analytic_lines',
                            move=move.rec_name,
                            account="[%s] %s" % (line.account.code,
                                line.account.name),
                            roots=', '.join(r.rec_name
                                for r in required_roots),
                            origin=origin,
                            origin_model=origin_model,
                            ))
                for analytic_line in line.analytic_lines:
                    if analytic_line.account.root in required_roots:
                        required_roots.remove(analytic_line.account.root)
                    constraint = line.account.analytic_constraint(
                        analytic_line.account)
                    if (constraint == 'required' and
                            analytic_line.state != 'valid'):
                        raise UserError(gettext(
                            'analytic_line_state.invalid_analytic_to_post_move',
                                move=move.rec_name,
                                line=line.rec_name,
                                root=analytic_line.account.root.rec_name,
                                ))
                if required_roots:
                    raise UserError(gettext(
                        'analytic_line_state.missing_analytic_lines',
                            move=move.rec_name,
                            account="[%s] %s" % (line.account.code,
                                line.account.name),
                            roots=', '.join(r.rec_name
                                for r in required_roots),
                            origin=origin,
                            origin_model=origin_model,
                            ))


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def check_modify(cls, lines, modified_fields=None):
        '''
        Check if the lines can be modified
        '''
        if modified_fields is None:
            return

        super(MoveLine, cls).check_modify(lines, modified_fields)

    @classmethod
    def validate(cls, lines):
        super(MoveLine, cls).validate(lines)
        for line in lines:
            line.check_account_analytic_configuration()

    def check_account_analytic_configuration(self):
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config(1)
        if config.validate_analytic:
            if self.account.analytic_pending_accounts:
                raise UserError(gettext(
                    'analytic_line_state.account_analytic_not_configured',
                        line=self.rec_name,
                        account=self.account.rec_name,
                        ))

    @classmethod
    def validate_analytic_lines(cls, lines):
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')

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
        AnalyticLine.write(todraft_lines, {
                'state': 'draft',
                })
        super(MoveLine, cls).delete(lines)

    @dualmethod
    def save(cls, lines):
        # XXX: as required move_line is dropped on analytic line,
        # this can be called with None value
        super(MoveLine, cls).save([x for x in lines if x])

    @classmethod
    def set_analytic_state(cls, lines):
        # XXX: as required move_line is dropped on analytic line,
        # this can be called with None value
        super(MoveLine, cls).set_analytic_state([x for x in lines if x])
