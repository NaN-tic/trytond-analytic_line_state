# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from sql import Column, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, PYSONEncoder, PYSONDecoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['AnalyticAccount', 'AnalyticAccountAccountRequired',
    'AnalyticAccountAccountForbidden', 'AnalyticAccountAccountOptional',
    'AnalyticLine', 'OpenChartAccountStart', 'OpenChartAccount']


class AnalyticAccount(metaclass=PoolMeta):
    __name__ = 'analytic_account.account'

    analytic_required = fields.Many2Many(
        'analytic_account.account-required-account.account',
        'analytic_account', 'account', 'Analytic Required', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            },
        depends=['company', 'analytic_forbidden', 'analytic_optional', 'type'])
    analytic_forbidden = fields.Many2Many(
        'analytic_account.account-forbidden-account.account',
        'analytic_account', 'account', 'Analytic Forbidden', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            },
        depends=['company', 'analytic_required', 'analytic_optional', 'type'])
    analytic_optional = fields.Many2Many(
        'analytic_account.account-optional-account.account',
        'analytic_account', 'account', 'Analytic Optional', domain=[
            ('type', '!=', None),
            ('company', '=', Eval('company')),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ], states={
            'invisible': Eval('type') != 'root',
            },
        depends=['company', 'analytic_required', 'analytic_forbidden', 'type'])
    analytic_pending_accounts = fields.Function(fields.Many2Many(
            'account.account', None, None, 'Pending Accounts', states={
                'invisible': Eval('type') != 'root',
                },
            depends=['type']),
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
            raise UserError(gettext(
                'analytic_line_state.analytic_account_required_forbidden',
                    root=self.rec_name,
                    accounts=', '.join([a.rec_name
                            for a in (required & forbidden)])
                    ))
        if required & optional:
            raise UserError(gettext(
                'analytic_line_state.analytic_account_required_optional',
                    root=self.rec_name,
                    accounts=', '.join([a.rec_name
                            for a in (required & optional)])
                    ))
        if forbidden & optional:
            raise UserError(gettext(
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
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        # Migration from 3.4: rename table
        old_table = 'analytic_account_account-required-account_account'
        new_table = 'analytic_acc_acc_required_acc_acc'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, new_table)
        super(AnalyticAccountAccountRequired, cls).__register__(
            module_name)


class AnalyticAccountAccountForbidden(ModelSQL):
    'Analytic Account - Account - Forbidden'
    __name__ = 'analytic_account.account-forbidden-account.account'
    _table = 'analytic_acc_acc_forbidden_acc_acc'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        # Migration from 3.4: rename table
        old_table = 'analytic_account_account-forbidden-account_account'
        new_table = 'analytic_acc_acc_forbidden_acc_acc'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, new_table)
        super(AnalyticAccountAccountForbidden, cls).__register__(
            module_name)


class AnalyticAccountAccountOptional(ModelSQL):
    'Analytic Account - Account - Optional'
    __name__ = 'analytic_account.account-optional-account.account'
    _table = 'analytic_acc_acc_optional_acc_acc'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        # Migration from 3.4: rename table
        old_table = 'analytic_account_account-optional-account_account'
        new_table = 'analytic_acc_acc_optional_acc_acc'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, new_table)
        super(AnalyticAccountAccountOptional, cls).__register__(
            module_name)


_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class AnalyticLine(metaclass=PoolMeta):
    __name__ = 'analytic_account.line'

    internal_company = fields.Many2One('company.company', 'Company',
        required=True, states=_STATES, depends=_DEPENDS)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ], 'State', required=True, readonly=True, select=True)

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
                field.depends.append('state')

        company_domain = ('account.company', '=', Eval('internal_company'))
        if not cls.move_line.domain:
            cls.move_line.domain = [company_domain]
        elif company_domain not in cls.move_line.domain:
            cls.move_line.domain.append(company_domain)

        cls.move_line.required = False
        cls.move_line.states = {
            'required': Eval('state') != 'draft',
            'readonly': Eval('state') != 'draft',
            }
        cls.move_line.depends += ['internal_company', 'state']


    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        account_sql_table = pool.get('account.account').__table__()
        move_line_sql_table = pool.get('account.move.line').__table__()

        copy_company = False
        if TableHandler.table_exist(cls._table):
            # if table doesn't exists => new db
            table = TableHandler(cls, module_name)
            copy_company = not table.column_exist('internal_company')

        super(AnalyticLine, cls).__register__(module_name)

        table = TableHandler(cls, module_name)

        is_sqlite = backend.name() == 'sqlite'
        # Migration from DB without this module
        # table.not_null_action('move_line', action='remove') don't execute the
        # action if the field is not defined in this module
        if not is_sqlite:
            cursor.execute('ALTER TABLE %s ALTER COLUMN "move_line" '
                'DROP NOT NULL' % (sql_table,))
            table._update_definitions()

        cursor.execute(*sql_table.update(columns=[sql_table.state],
                values=['posted'],
                where=((sql_table.state == Null) &
                    (sql_table.move_line == Null))))
        if copy_company and not is_sqlite:
            join = move_line_sql_table.join(account_sql_table)
            join.condition = move_line_sql_table.account == join.right.id
            query = sql_table.update(columns=[sql_table.internal_company],
                    values=[join.right.company], from_=[join],
                    where=sql_table.move_line == join.left.id)
            cursor.execute(*query)

    @staticmethod
    def default_internal_company():
        return Transaction().context.get('company')

    @fields.depends('internal_company')
    def on_change_with_currency_digits(self, name=None):
        digits = super(AnalyticLine, self).on_change_with_currency_digits(
            name=name)
        if self.internal_company:
            digits = self.internal_company.currency.digits
        return digits

    @fields.depends('internal_company')
    def on_change_with_company(self, name=None):
        if self.internal_company:
            return self.internal_company.id

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
            raise UserError(gettext(
                'analytic_line_state.move_line_account_analytic_forbidden',
                    line=self.rec_name,
                    account=self.move_line.account.rec_name,
                    ))

    @classmethod
    def check_modify(cls, lines):
        '''
        Check if the lines can be modified
        '''
        MoveLine = Pool().get('account.move.line')
        move_lines = [l.move_line for l in lines if l.move_line]
        MoveLine.check_modify(list(set(move_lines)))

    @classmethod
    def create(cls, vlist):
        MoveLine = Pool().get('account.move.line')

        lines = super(AnalyticLine, cls).create(vlist)
        cls.check_modify(lines)

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
        cls.check_modify(lines_to_check)

        move_lines = set([l.move_line for l in all_lines if l.move_line])
        super(AnalyticLine, cls).write(*args)
        move_lines |= set([l.move_line for l in all_lines if l.move_line])

        lines_to_check = []
        for lines, vals in zip(actions, actions):
            if any(k not in cls._check_modify_exclude for k in vals):
                lines_to_check.extend(lines)
        cls.check_modify(lines_to_check)
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

        cls.check_modify(lines)

        move_lines = list(set([l.move_line for l in lines if l.move_line]))
        super(AnalyticLine, cls).delete(lines)
        MoveLine.validate_analytic_lines(move_lines)


class OpenChartAccountStart(ModelView):
    __name__ = 'analytic_account.open_chart.start'
    posted = fields.Boolean('Posted Moves',
        help='Show posted moves only')


class OpenChartAccount(Wizard):
    __name__ = 'analytic_account.open_chart'

    def do_open_(self, action):
        action, context = super(OpenChartAccount, self).do_open_(action)
        pyson_context = PYSONDecoder().decode(action['pyson_context'])
        pyson_context.update({
                'posted': self.start.posted,
                'date': self.start.end_date,
                })
        action['pyson_context'] = PYSONEncoder().encode(pyson_context)
        return action, context

# vim:ft=python.tryton:
