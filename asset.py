# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError
from trytond.i18n import gettext


class UpdateAsset(metaclass=PoolMeta):
    'Update Asset'
    __name__ = 'account.asset.update'

    def get_move_lines(self, asset):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')
        AnalyticAccount = pool.get('analytic_account.account')
        MoveLine = pool.get('account.move.line')

        lines = super().get_move_lines(asset)

        if not lines:
            return lines

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
