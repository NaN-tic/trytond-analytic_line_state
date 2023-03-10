# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext


class UpdateAsset(metaclass=PoolMeta):
    __name__ = 'account.asset.update'

    def get_move_lines(self, asset):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')
        AnalyticAccount = pool.get('analytic_account.account')
        MoveLine = pool.get('account.move.line')

        lines = super().get_move_lines(asset)
        if not lines:
            return lines

        # set analytic lines because is required when post move
        self.set_analytic_lines(lines, asset)

        # analytic_account_move extras depend
        analytic_account_move = (True if hasattr(MoveLine, 'analytic_accounts')
            else False)
        if asset.analytic_accounts and analytic_account_move:
            for line in lines:
                if line.account and not line.account.analytic_required:
                    continue
                entries = []
                roots = [x.id for x in line.account.analytic_required]
                aroots = [x.root.id for x in asset.analytic_accounts]
                missing_roots = set(set(roots)-set(aroots))
                if missing_roots:
                    raise UserError(gettext('account_asset_analytic_line_state'
                            '.msg_missing_root_on_asset',
                            roots=", ".join([AnalyticAccount(x).name
                                    for x in missing_roots]),
                            account=line.account.code,
                            asset=asset.number))
                for aline in asset.analytic_accounts:
                    if aline.root.id not in roots:
                        continue
                    entry = AnalyticAccountEntry()
                    entry.root = aline.root
                    entry.account = aline.account
                    entries.append(entry)
                line.analytic_accounts = entries
        return lines

    def set_analytic_lines(self, lines, asset):
        "Fill analytic lines on lines with given account"
        account = asset.product.account_expense_used
        if asset.analytic_accounts:
            with Transaction().set_context(date=self.show_move.date):
                for line in lines:
                    if line.account != account:
                        continue
                    analytic_lines = []
                    for entry in asset.analytic_accounts:
                        analytic_lines.extend(
                            entry.get_analytic_lines(line, self.show_move.date))
                    line.analytic_lines = analytic_lines
