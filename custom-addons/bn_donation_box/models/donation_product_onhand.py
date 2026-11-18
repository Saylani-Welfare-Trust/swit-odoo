from odoo import fields, models, tools
from odoo.tools.sql import TableKind, table_kind


class DonationProductOnhand(models.Model):
    """On-hand quantity of the donation box products per internal location:
    a database view over the stock quants (one row per product and
    location), so the list searches, filters and groups like any other.
    Who sees which locations follows the stock scope rules
    (security/stock_scope_rule.xml)."""
    _name = 'donation.product.onhand'
    _description = 'Donation Product On-hand Quantity'
    _auto = False
    _log_access = False
    _order = 'location_id, product_id'

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Branch', readonly=True)
    on_hand_qty = fields.Float(string='On-Hand Quantity', readonly=True, digits='Product Unit of Measure')

    def init(self):
        # earlier versions kept it as a (always empty) table
        if table_kind(self.env.cr, self._table) == TableKind.Regular:
            self.env.cr.execute('DROP TABLE "%s" CASCADE' % self._table)
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT MIN(q.id) AS id,
                       q.product_id,
                       q.location_id,
                       l.analytic_account_id,
                       SUM(q.quantity - q.reserved_quantity) AS on_hand_qty
                  FROM stock_quant q
                  JOIN stock_location l ON l.id = q.location_id AND l.usage = 'internal'
                  JOIN product_product p ON p.id = q.product_id
                  JOIN product_template t ON t.id = p.product_tmpl_id AND t.is_donation_box
                 GROUP BY q.product_id, q.location_id, l.analytic_account_id
            )
        """ % self._table)
