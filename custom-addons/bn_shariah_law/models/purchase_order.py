from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)