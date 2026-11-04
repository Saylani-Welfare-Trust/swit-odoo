from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    net_amount = fields.Monetary(
        string="Net Amount",
        compute="_compute_net_amount",
        store=True,
        currency_field="currency_id",
        help="Amount that is actually paid by cheque.",
    )

    @api.depends("amount")
    def _compute_net_amount(self):
        for payment in self:
            # If bn_wht_customization (or any other module) later
            # provides a WHT-aware value, override this method.
            payment.net_amount = payment.amount

    cheque_print_mode = fields.Selection(
        [
            ('ac_payee_only', 'A/C Payee Only'),
            ('cash', 'Cash'),
            ('bearer', 'Bearer'),
        ],
        string="Cheque Print Mode",
        default='ac_payee_only',
    )

    def action_print_check(self):
        configs = self.env['bank.cheque.config'].search(
            [('journal_ids', 'in', [self.journal_id.id])]
        )
        if not configs:
            raise UserError(
                "No Bank Cheque Configuration is linked to this journal."
            )
        configs.ensure_one()
        return configs.action_print_cheque_for_payment(self)

    @api.depends('payment_method_line_id', 'currency_id', 'net_amount')
    def _compute_check_amount_in_words(self):
        super()._compute_check_amount_in_words()
        # ... existing body unchanged ...