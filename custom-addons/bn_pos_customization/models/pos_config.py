from odoo import models, fields


class POSConfig(models.Model):
    _inherit = 'pos.config'

    user_ids = fields.Many2many('res.users', string="Users")
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 
        string="Branch Analytic Account",
        help="Select the branch analytic account to print on the POS receipt."
    )