# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from sql import Column
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.model.exceptions import ValidationError


class AnalyticAccount(metaclass=PoolMeta):
    __name__ = 'analytic_account.account'

    analytic_required = fields.Many2Many(
        'analytic_account.account-required-account.account',
        'analytic_account', 'account', 'Analytic Required', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company', -1)),
            ('id', 'not in', Eval('analytic_forbidden')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            })
    analytic_forbidden = fields.Many2Many(
        'analytic_account.account-forbidden-account.account',
        'analytic_account', 'account', 'Analytic Forbidden', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company', -1)),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            })
    analytic_optional = fields.Many2Many(
        'analytic_account.account-optional-account.account',
        'analytic_account', 'account', 'Analytic Optional', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company', -1)),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ], states={
            'invisible': Eval('type') != 'root',
            })
    analytic_pending_accounts = fields.Function(fields.Many2Many(
            'account.account', None, None, 'Pending Accounts', states={
                'invisible': Eval('type') != 'root',
                }),
        'on_change_with_analytic_pending_accounts')

    @fields.depends('analytic_required', 'analytic_forbidden',
        'analytic_optional', 'company')
    def on_change_with_analytic_pending_accounts(self, name=None):
        Account = Pool().get('account.account')

        current_accounts = [x.id for x in self.analytic_required]
        current_accounts += [x.id for x in self.analytic_forbidden]
        current_accounts += [x.id for x in self.analytic_optional]
        pending_accounts = Account.search([
                ('type', '!=', None),
                ('company', '=', self.company),
                ('id', 'not in', current_accounts),
                ])
        return [x.id for x in pending_accounts]

    @classmethod
    def query_get(cls, ids, names):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        Company = pool.get('company.company')
        table = cls.__table__()
        line = Line.__table__()
        company = Company.__table__()

        line_query = Line.query_get(line)

        columns = [table.id, company.currency]
        for name in names:
            if name == 'balance':
                columns.append(
                    Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)))
            else:
                columns.append(Sum(Coalesce(Column(line, name), 0)))
        query = table.join(line, 'LEFT',
            condition=table.id == line.account
            ).join(company, 'LEFT',
            condition=company.id == line.internal_company
            ).select(*columns,
            where=(table.type != 'view')
            & table.id.in_(ids)
            & table.active & line_query,
            group_by=(table.id, company.currency))
        return query

    @classmethod
    def validate(cls, accounts):
        super(AnalyticAccount, cls).validate(accounts)
        for account in accounts:
            account.check_analytic_accounts()

    def check_analytic_accounts(self):
        required = set(self.analytic_required)
        forbidden = set(self.analytic_forbidden)
        optional = set(self.analytic_optional)
        if required & forbidden:
            raise ValidationError(gettext(
                'analytic_line_state.analytic_account_required_forbidden',
                    root=self.rec_name,
                    accounts=', '.join([a.rec_name
                            for a in (required & forbidden)])
                    ))
        if required & optional:
            raise ValidationError(gettext(
                'analytic_line_state.analytic_account_required_optional',
                    root=self.rec_name,
                    accounts=', '.join([a.rec_name
                            for a in (required & optional)])
                    ))
        if forbidden & optional:
            raise ValidationError(gettext(
                'analytic_line_state.analytic_account_forbidden_optional',
                    root=self.rec_name,
                    accounts=', '.join([a.rec_name
                            for a in (forbidden & optional)])
                    ))


class AnalyticAccountAccountRequired(ModelSQL):
    'Analytic Account - Account - Required'
    __name__ = 'analytic_account.account-required-account.account'
    _table = 'analytic_acc_acc_required_acc_acc'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True)


class AnalyticAccountAccountForbidden(ModelSQL):
    'Analytic Account - Account - Forbidden'
    __name__ = 'analytic_account.account-forbidden-account.account'
    _table = 'analytic_acc_acc_forbidden_acc_acc'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True)


class AnalyticAccountAccountOptional(ModelSQL):
    'Analytic Account - Account - Optional'
    __name__ = 'analytic_account.account-optional-account.account'
    _table = 'analytic_acc_acc_optional_acc_acc'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True)


_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class AnalyticLine(metaclass=PoolMeta):
    __name__ = 'analytic_account.line'

    internal_company = fields.Many2One('company.company', 'Company',
        required=True, states=_STATES)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ], 'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(AnalyticLine, cls).__setup__()
        cls._check_modify_exclude = ['state']
        for fname in ['debit', 'credit', 'account', 'date']:
            field = getattr(cls, fname)
            if field.states.get('readonly'):
                field.states['readonly'] = Or(field.states['readonly'],
                    _STATES['readonly'])
            else:
                field.states['readonly'] = _STATES['readonly']
            if 'state' not in field.depends:
                field.depends.add('state')

        company_domain = ('account.company', '=', Eval('internal_company', -1))
        if not cls.move_line.domain:
            cls.move_line.domain = [company_domain]
        elif company_domain not in cls.move_line.domain:
            cls.move_line.domain.append(company_domain)

        cls.move_line.required = False
        cls.move_line.states = {
            'required': Eval('state') != 'draft',
            'readonly': Eval('state') != 'draft',
            }
        cls.move_line.depends |= {'internal_company', 'state'}

    @staticmethod
    def default_internal_company():
        return Transaction().context.get('company')

    @fields.depends('internal_company')
    def on_change_with_company(self, name=None):
        if self.internal_company:
            return self.internal_company.id
        return super(AnalyticLine, self).on_change_with_company(name=name)

    @classmethod
    def search_company(cls, name, clause):
        return [('internal_company',) + tuple(clause[1:])]

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def query_get(cls, table):
        '''
        Return SQL clause for analytic line depending of the context.
        table is the SQL instance of the analytic_account_line table.
        '''
        clause = super(AnalyticLine, cls).query_get(table)
        if Transaction().context.get('posted'):
            clause &= table.state == 'posted'
        return clause

    @classmethod
    def validate(cls, lines):
        super(AnalyticLine, cls).validate(lines)
        for line in lines:
            line.check_account_forbidden_analytic()

    def check_account_forbidden_analytic(self):
        if (self.move_line and
                self.move_line.account.analytic_constraint(self.account)
                == 'forbidden'):
            raise ValidationError(gettext(
                'analytic_line_state.move_line_account_analytic_forbidden',
                    line=self.rec_name,
                    account=self.move_line.account.rec_name,
                    ))

    @classmethod
    def create(cls, vlist):
        MoveLine = Pool().get('account.move.line')

        lines = super(AnalyticLine, cls).create(vlist)

        move_lines = list(set(l.move_line for l in lines if l.move_line))
        MoveLine.validate_analytic_lines(move_lines)
        return lines

    @classmethod
    def write(cls, *args):
        MoveLine = Pool().get('account.move.line')

        actions = iter(args)
        lines_to_check, all_lines = [], []
        for lines, vals in zip(actions, actions):
            if any(k not in cls._check_modify_exclude for k in vals):
                lines_to_check.extend(lines)
            all_lines.extend(lines)

        move_lines = set([l.move_line for l in all_lines if l.move_line])
        super(AnalyticLine, cls).write(*args)
        move_lines |= set([l.move_line for l in all_lines if l.move_line])

        lines_to_check = []
        for lines, vals in zip(actions, actions):
            if any(k not in cls._check_modify_exclude for k in vals):
                lines_to_check.extend(lines)
        MoveLine.validate_analytic_lines(list(move_lines))
        todraft_lines = [l for l in all_lines
            if (not l.move_line and l.state != 'draft')]
        # Call super to avoid_recursion error:
        if todraft_lines:
            super(AnalyticLine, cls).write(todraft_lines, {
                    'state': 'draft',
                    })

    @classmethod
    def delete(cls, lines):
        MoveLine = Pool().get('account.move.line')

        move_lines = list(set([l.move_line for l in lines if l.move_line]))
        super(AnalyticLine, cls).delete(lines)
        MoveLine.validate_analytic_lines(move_lines)
