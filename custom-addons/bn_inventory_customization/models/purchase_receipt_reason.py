from odoo import fields, models


class PurchaseReceiptReason(models.Model):
    _name = 'purchase.receipt.reason'
    _description = 'Purchase Receipt Reason'
    _order = 'date desc, id desc'

    order_id = fields.Many2one('purchase.order', string='Purchase Order', required=True,
                               ondelete='cascade', index=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Receipt', readonly=True)
    reason_type = fields.Selection([
        ('no_backorder', 'No Backorder'),
        ('cancel', 'Receipt Cancelled'),
    ], string='Action', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='By', default=lambda self: self.env.user, readonly=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, readonly=True)
