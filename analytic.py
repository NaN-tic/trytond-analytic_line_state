# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from sql import Column
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.model import Model, ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, PYSONEncoder, If, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard

__all__ = ['AnalyticAccount', 'AnalyticAccountAccountRequired',
    'AnalyticAccountAccountForbidden', 'AnalyticAccountAccountOptional',
    'AnalyticLine', 'OpenChartAccountStart', 'OpenChartAccount']
__metaclass__ = PoolMeta


class AnalyticAccount:
    __name__ = 'analytic_account.account'

    analytic_required = fields.Many2Many(
        'analytic_account.account-required-account.account',
        'analytic_account', 'account', 'Analytic Required', domain=[
            ('kind', '!=', 'view'),
            ('id', 'not in', Eval('analytic_forbidden')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            }, depends=['analytic_forbidden', 'analytic_optional', 'type'])
    analytic_forbidden = fields.Many2Many(
        'analytic_account.account-forbidden-account.account',
        'analytic_account', 'account', 'Analytic Forbidden', domain=[
            ('kind', '!=', 'view'),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_optional')),
            ], states={
            'invisible': Eval('type') != 'root',
            }, depends=['analytic_required', 'analytic_optional', 'type'])
    analytic_optional = fields.Many2Many(
        'analytic_account.account-optional-account.account',
        'analytic_account', 'account', 'Analytic Optional', domain=[
            ('kind', '!=', 'view'),
            ('id', 'not in', Eval('analytic_required')),
            ('id', 'not in', Eval('analytic_forbidden')),
            ], states={
            'invisible': Eval('type') != 'root',
            }, depends=['analytic_required', 'analytic_forbidden', 'type'])
    analytic_pending_accounts = fields.Function(fields.Many2Many(
            'account.account', None, None, 'Pending Accounts', states={
                'invisible': Eval('type') != 'root',
                },
            depends=['type']),
        'on_change_with_analytic_pending_accounts')

    @classmethod
    def __setup__(cls):
        super(AnalyticAccount, cls).__setup__()
        cls._error_messages.update({
                'analytic_account_required_forbidden': (
                    'The next accounts are configured as Required and '
                    'Forbidden for the Analytic Root "%(root)s": '
                    '%(accounts)s.'),
                'analytic_account_required_optional': (
                    'The next accounts are configured as Required and '
                    'Optional for the Analytic Root "%(root)s": '
                    '%(accounts)s.'),
                'analytic_account_forbidden_optional': (
                    'The next accounts are configured as Forbidden and '
                    'Optional for the Analytic Root "%(root)s": '
                    '%(accounts)s.'),
                })

    @fields.depends('analytic_required', 'analytic_forbidden',
        'analytic_optional')
    def on_change_with_analytic_pending_accounts(self, name=None):
        Account = Pool().get('account.account')

        current_accounts = map(int, self.analytic_required)
        current_accounts += map(int, self.analytic_forbidden)
        current_accounts += map(int, self.analytic_optional)
        pending_accounts = Account.search([
                ('kind', '!=', 'view'),
                ('id', 'not in', current_accounts),
                ])
        return map(int, pending_accounts)

    @classmethod
    def _query_get(cls, ids, name):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        table = cls.__table__()
        line = Line.__table__()

        join = table.join(line, 'LEFT',
                condition=table.id == line.account
                )

        line_query = Line.query_get(line)
        if name == 'balance':
            return join.select(table.id,
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                line.internal_currency,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & table.active & line_query,
                group_by=(table.id, line.internal_currency))
        elif name in ('credit', 'debit'):
            return join.select(table.id,
                Sum(Coalesce(Column(line, name), 0)),
                line.internal_currency,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & table.active & line_query,
                group_by=(table.id, line.internal_currency))
        return None

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
            self.raise_user_error('analytic_account_required_forbidden', {
                    'root': self.rec_name,
                    'accounts': ', '.join([a.rec_name
                            for a in (required & forbidden)])
                    })
        if required & optional:
            self.raise_user_error('analytic_account_required_optional', {
                    'root': self.rec_name,
                    'accounts': ', '.join([a.rec_name
                            for a in (required & optional)])
                    })
        if forbidden & optional:
            self.raise_user_error('analytic_account_forbidden_optional', {
                    'root': self.rec_name,
                    'accounts': ', '.join([a.rec_name
                            for a in (forbidden & optional)])
                    })


class AnalyticAccountAccountRequired(ModelSQL):
    'Analytic Account - Account - Required'
    __name__ = 'analytic_account.account-required-account.account'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)


class AnalyticAccountAccountForbidden(ModelSQL):
    'Analytic Account - Account - Forbidden'
    __name__ = 'analytic_account.account-forbidden-account.account'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)


class AnalyticAccountAccountOptional(ModelSQL):
    'Analytic Account - Account - Optional'
    __name__ = 'analytic_account.account-optional-account.account'
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', ondelete='CASCADE', required=True, select=True,
        domain=[('type', '=', 'root')])
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', required=True, select=True)


_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class AnalyticLine:
    __name__ = 'analytic_account.line'

    internal_currency = fields.Many2One('currency.currency',
        'Currency (Internal)', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ], 'State', required=True, readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(AnalyticLine, cls).__setup__()
        cls._check_modify_exclude = ['state']
        for fname in ('name', 'debit', 'credit', 'account', 'journal', 'date',
                'reference', 'party', 'active', 'currency'):
            field = getattr(cls, fname)
            if field.states.get('readonly'):
                field.states['readonly'] = Or(field.states['readonly'],
                    _STATES['readonly'])
            else:
                field.states['readonly'] = _STATES['readonly']
            if 'state' not in field.depends:
                field.depends.append('state')
        cls.currency.readonly = False
        cls.currency.setter = 'set_currency'
        cls.currency_digits.on_change_with = ['internal_currency']

        cls.move_line.required = False
        cls.move_line.states = {
            'required': Eval('state') != 'draft',
            'readonly': Eval('state') != 'draft',
            }
        if not 'move_line' in cls.account.depends:
            old_domain = cls.account.domain
            company_domain = old_domain.pop()
            cls.account.domain = [old_domain,
                If(Bool(Eval('move_line', 0)),
                    [company_domain],
                    [()])
                ]
            cls.account.depends.append('move_line')
        if not cls.move_line.on_change:
            cls.move_line.on_change = []
        for name in ['move_line', 'journal', 'name', 'party', 'debit',
                'credit']:
            if not name in cls.move_line.on_change:
                cls.move_line.on_change.append(name)

        cls._error_messages.update({
                'different_currency_move': ('Currency of analytic line "%s" '
                    'is different from the one of the related move line.'),
                'move_line_account_analytic_forbidden': (
                    'The Analytic Line "%(line)s" is related to an Account '
                    'Move Line of Account "%(account)s" which has the '
                    'analytics forbidden for the Line\'s Analytic hierarchy.'),
                })
        cls._buttons.update({
                'post': {
                    'invisible': Eval('state') == 'posted',
                    },
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        sql_table = cls.__table__()
        account_sql_table = pool.get('account.account').__table__()
        company_sql_table = pool.get('company.company').__table__()
        move_line_sql_table = pool.get('account.move.line').__table__()

        copy_currency = False
        if TableHandler.table_exist(cursor, cls._table):
            # if table doesn't exists => new db
            table = TableHandler(cursor, cls, module_name)
            copy_currency = not table.column_exist('internal_currency')

        super(AnalyticLine, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        is_sqlite = 'backend.sqlite.table.TableHandler' in str(TableHandler)
        # Migration from DB without this module
        #table.not_null_action('move_line', action='remove') don't execute the
        # action if the field is not defined in this module
        if not is_sqlite:
            cursor.execute('ALTER TABLE %s ALTER COLUMN "move_line" '
                'DROP NOT NULL' % (sql_table,))
            table._update_definitions()

        cursor.execute(*sql_table.update(columns=[sql_table.state],
                values=['posted'],
                where=((sql_table.state == None) &
                    (sql_table.move_line == None))))
        if copy_currency and not is_sqlite:
            join = move_line_sql_table.join(account_sql_table)
            join.condition = move_line_sql_table.account == join.right.id
            join2 = join.join(company_sql_table)
            join2.condition = join.right.company == join2.right.id
            query = sql_table.update(columns=[sql_table.internal_currency],
                    values=[join2.right.currency], from_=[join2],
                    where=sql_table.move_line == join.left.id)
            cursor.execute(*query)

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @fields.depends('internal_currency')
    def on_change_with_currency(self, name=None):
        if self.internal_currency:
            return self.internal_currency.id

    @classmethod
    def set_currency(cls, lines, name, value):
        cls.write(lines, {
                'internal_currency': value,
                })

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @staticmethod
    def default_state():
        return 'draft'

    def default_move_line_field(field_name):
        @staticmethod
        def default_value():
            return Transaction().context.get(field_name)
        return default_value

    default_debit = default_move_line_field('debit')
    default_credit = default_move_line_field('credit')
    default_journal = default_move_line_field('journal')
    default_party = default_move_line_field('party')

    @staticmethod
    def default_date():
        context = Transaction().context
        value = context.get('date')
        if value:
            return value
        if 'move' in context:
            move = Pool().get('account.move')(context.get('move'))
            return move.date

    @staticmethod
    def default_name():
        context = Transaction().context
        for name in ('description', 'move_description'):
            value = context.get('description')
            if value:
                return value
        if 'move' in context:
            move = Pool().get('account.move')(context.get('move'))
            return move.description

    def on_change_move_line(self):
        res = {
            'journal': None,
            'name': None,
            'party': None,
            }
        if not self.move_line:
            return res

        res['date'] = self.move_line.move.date
        if not self.debit:
            res['debit'] = self.move_line.debit
        if not self.credit:
            res['credit'] = self.move_line.credit
        if not self.journal:
            res['journal'] = self.move_line.move.journal.id
        if not self.party and self.move_line.party:
            res['party'] = self.move_line.party.id
        if not self.name:
            res['name'] = self.move_line.description
        return res

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
            line.check_currency()
            line.check_account_forbidden_analytic()

    def check_currency(self):
        if self.move_line:
            move_currency = self.move_line.account.currency
            if move_currency != self.currency:
                self.raise_user_error('different_currency_move', self.rec_name)

    def check_account_forbidden_analytic(self):
        if (self.move_line and
                self.move_line.account.analytic_constraint(self.account)
                == 'forbidden'):
            self.raise_user_error('move_line_account_analytic_forbidden', {
                    'line': self.rec_name,
                    'account': self.move_line.account.rec_name,
                    })

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
    def write(cls, lines, vals):
        MoveLine = Pool().get('account.move.line')

        if any(k not in cls._check_modify_exclude for k in vals):
            cls.check_modify(lines)

        move_lines = [l.move_line for l in lines if l.move_line]
        super(AnalyticLine, cls).write(lines, vals)
        move_lines += [l.move_line for l in lines if l.move_line]

        if any(k not in cls._check_modify_exclude for k in vals):
            cls.check_modify(lines)

            MoveLine.validate_analytic_lines(list(set(move_lines)))
            todraft_lines = [l for l in lines
                if (not l.move_line and l.state != 'draft')]
            cls.write(todraft_lines, {
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
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': self.start.start_date,
                'end_date': self.start.end_date,
                'posted': self.start.posted,
                })
        return action, context

# vim:ft=python.tryton:
