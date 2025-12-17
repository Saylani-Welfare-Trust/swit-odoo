from odoo import models, fields


class HRExpense(models.Model):
    _inherit = 'hr.expense'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)