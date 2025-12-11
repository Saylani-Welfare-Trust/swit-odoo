from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)