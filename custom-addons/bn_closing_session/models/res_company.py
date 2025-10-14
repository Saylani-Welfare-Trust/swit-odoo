from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    account_default_pos_restricted_receivable_account_id = fields.Many2one(
        'account.account',
        string='Restricted Receivable Account',
        # domain=[('reconcile', '=', True),('account_type', '=', 'asset_receivable')],
        help="Account for restricted receivable amounts"
    )

    account_default_pos_unrestricted_receivable_account_id = fields.Many2one(
        'account.account',
        string='Unrestricted Receivable Account',
        # domain=[('reconcile', '=', True),('account_type', '=', 'asset_receivable')],
        help="Account for unrestricted receivable amounts"
    )