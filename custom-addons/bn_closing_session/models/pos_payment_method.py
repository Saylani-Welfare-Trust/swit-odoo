from odoo import models, fields


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'


    restricted_account_id = fields.Many2one(
        'account.account',
        string='Restricted Receivable Account',
        # domain=[('reconcile', '=', True),('account_type', '=', 'asset_receivable')],
        help="Account for restricted receivable amounts"
    )

    unrestricted_account_id = fields.Many2one(
        'account.account',
        string='Unrestricted Receivable Account',
        # domain=[('reconcile', '=', True),('account_type', '=', 'asset_receivable')],
        help="Account for unrestricted receivable amounts"
    )

    neutral_account_id = fields.Many2one(
        'account.account',
        string='Neutral Receivable Account',
        # domain=[('reconcile', '=', True),('account_type', '=', 'asset_receivable')],
        help="Account for neutral receivable amounts"
    )