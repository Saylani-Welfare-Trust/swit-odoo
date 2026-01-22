from odoo import models, fields


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'


    skip_amount_input = fields.Boolean(
        string='Skip Amount Input in Closing',
        help="If checked, this payment method will not require slip number and payment breakdown in closing session. All payments will be managed as a single total, like the default Odoo flow."
    )


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

    