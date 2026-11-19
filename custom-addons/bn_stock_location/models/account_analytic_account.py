from odoo import api, models
from odoo.osv import expression


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.model
    def _search(self, domain, *args, **kwargs):
        """Branch pickers: with ``branch_scope`` in the context (set on the field
        in the view), offer only the user's analytic accounts in scope
        (res.users.scope_analytic_account_ids). Only a convenience: the record
        rules are what restrict the records. Administrators and "Unrestricted
        Access" see every account."""
        if self.env.context.get('branch_scope') and not self.env.su:
            user = self.env.user
            if not (user.has_group('base.group_system')
                    or user.has_group('bn_stock_location.stock_scope_unrestricted_group')):
                domain = expression.AND([domain or [], [('id', 'in', user.scope_analytic_account_ids.ids)]])
        return super()._search(domain, *args, **kwargs)
