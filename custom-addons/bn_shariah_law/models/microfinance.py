from odoo import models, fields


class Microfinance(models.Model):
    _inherit = 'microfinance'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)