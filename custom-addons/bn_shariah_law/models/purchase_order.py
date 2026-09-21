from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)
    shariah_override = fields.Boolean(
        'Shariah Balance Overridden', copy=False, tracking=True,
        help='Set once the CFO has approved this order despite it exceeding the Shariah Law closing balance.')


    @api.model
    def _get_product_segment(self, product):
        """The analytic account (segment) of a product: the one set on the product
        itself, otherwise the one whose Products list contains it."""
        analytic = self.env['account.analytic.account']
        if 'analytic_account_id' in product._fields:
            analytic = product.analytic_account_id
        return analytic or analytic.search([('product_ids', 'in', [product.id])], limit=1)

    def _get_shariah_amounts(self):
        """{analytic account id: amount} - the Subtotal of this order's lines added
        up per segment (the analytic account of each line's product)."""
        self.ensure_one()
        amounts = {}
        for line in self.order_line:
            if not line.product_id:
                continue
            analytic_account = self._get_product_segment(line.product_id)
            if analytic_account:
                amounts[analytic_account.id] = amounts.get(analytic_account.id, 0.0) + line.price_subtotal
        return amounts

    def _get_shariah_shortfalls(self):
        """Segments whose Shariah Law closing balance is below what this order's
        lines commit to them.

        Each line goes to the analytic account (segment) of its product, and
        the lines' Subtotal amounts are added up per segment and compared with
        that segment's closing balance. Returns [(analytic account, required,
        closing balance)]; empty when the Purchase Orders blocker is switched off."""
        self.ensure_one()
        blocker = self.env['shariah.law.blocker'].get_blocker_config()
        if not (blocker and blocker.enable_purchase):
            return []
        return self.env['shariah.law'].get_shortfalls(self._get_shariah_amounts())

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
