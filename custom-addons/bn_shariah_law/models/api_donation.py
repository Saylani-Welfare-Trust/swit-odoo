from odoo import models, fields


class APIDonation(models.Model):
    _inherit = 'api.donation'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)