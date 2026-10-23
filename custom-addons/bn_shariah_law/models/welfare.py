from odoo import models, fields


class Welfare(models.Model):
    _inherit = 'welfare'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)