from odoo import models, fields


class Donation(models.Model):
    _inherit = 'donation'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)