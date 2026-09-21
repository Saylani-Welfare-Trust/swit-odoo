from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)
    shariah_override = fields.Boolean(
        'Shariah Balance Overridden', copy=False, tracking=True,
        help='Set once the CFO has approved this order despite it exceeding the Shariah Law closing balance.')


    def _get_shariah_shortfalls(self):
        """Segments whose Shariah Law closing balance is below this order's amount.

        Returns [(analytic account, required, closing balance)]; empty when the
        Purchase Orders blocker is switched off."""
        self.ensure_one()
        blocker = self.env['shariah.law.blocker'].get_blocker_config()
        if not (blocker and blocker.enable_purchase):
            return []
        amounts = {}
        for line in self.order_line:
            analytic_account = self.env['account.analytic.account'].search([('product_ids', 'in', [line.product_id.id])], limit=1)
            if analytic_account:
                amounts[analytic_account.id] = self.amount_total
        return self.env['shariah.law'].get_shortfalls(amounts)

    def button_confirm(self):
        """
        Override the button_confirm method to include Shariah Law Blocker check.
        """
        for order in self:
            if order.shariah_override:
                continue
            for analytic_account, required, balance in order._get_shariah_shortfalls():
                raise models.ValidationError(
                    f"Purchase order amount {required} exceeds the closing balance {balance} for segment '{analytic_account.name}'."
                )

        return super(PurchaseOrder, self).button_confirm()
