from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)


    def button_confirm(self):
        """
        Override the button_confirm method to include Shariah Law Blocker check.
        """
        # Get blocker configuration
        blocker = self.env['shariah.law.blocker'].get_blocker_config()

        if blocker and blocker.enable_purchase:
            for order in self:
                if order.order_line:
                    for line in order.order_line:
                        analytic_account = self.env['account.analytic.account'].search([('product_ids', 'in', [line.product_id.id])], limit=1)

                        if analytic_account:
                            shariah_closing_balance = self.env['shariah.law'].get_closing_balance(analytic_account.id)
                            
                            if self.amount_total > shariah_closing_balance:
                                raise models.ValidationError(
                                    f"Purchase order amount {self.amount_total} exceeds the closing balance {shariah_closing_balance} for segment '{analytic_account.name}'."
                                )
        
        return super(PurchaseOrder, self).button_confirm()