# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountPayment(models.Model):
    _inherit = 'account.payment'    

    # ⚡ FIX: Add these missing fields so Odoo view validation doesn't crash
    effective_date = fields.Date(string="Effective Date")
    bank_reference = fields.Char(string="Bank Reference")
    cheque_reference = fields.Char(string="Cheque Reference")

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

        for pay in self:
            if not pay.currency_id:
                pay.check_amount_in_words = False
                continue

            amount = abs(pay.net_amount)
            rupees = int(amount)
            paisa = int(round((amount - rupees) * 100))

            words = pay.currency_id.amount_to_text(rupees) or ""

            # Cleanup
            words = (
                pay.currency_id.amount_to_text(rupees)
                .replace("Rupees", "")
                .replace("Rupee", "")
                .replace(",", "")
                .replace("-", " ")
                .strip()
            )

            words = " ".join(words.split()).lower()
            words = words.replace(" and ", " ")

            remainder = rupees % 1000

            if paisa == 0:
                if 0 < remainder < 100 and rupees >= 1000:
                    for unit in ("thousand", "lakh", "crore", "million"):
                        if unit in words:
                            words = words.replace(unit, unit + " and", 1)
                            break
                elif remainder in (100, 200, 300, 400, 500, 600, 700, 800, 900):
                    for unit in ("thousand", "lakh", "crore", "million"):
                        if unit in words:
                            words = words.replace(unit, unit + " and", 1)
                            break
                elif remainder > 100 and remainder % 100 != 0:
                    parts = words.split()
                    if "hundred" in parts:
                        idx = len(parts) - 1 - parts[::-1].index("hundred")
                        if idx + 1 < len(parts):
                            parts.insert(idx + 1, "and")
                    words = " ".join(parts)

                pay.check_amount_in_words = words.capitalize() + " only"
    
            else:
                paisa_words = pay.currency_id.amount_to_text(paisa) or ""
                paisa_words = (
                    paisa_words.replace("Rupees", "")
                               .replace("Rupee", "")
                               .replace(",", "")
                               .replace("-", " ")
                               .replace(" And ", " ")
                               .replace(" and ", " ")
                               .strip()
                )
                paisa_words = " ".join(paisa_words.split()).lower()

                pay.check_amount_in_words = (
                    f"{words.capitalize()} and {paisa_words} paisa only"
                )
                
    show_double_cheque = fields.Boolean(compute="_compute_show_double_cheque")

    @api.depends('journal_id')
    def _compute_show_double_cheque(self):
        for rec in self:
            if not rec.journal_id:
                rec.show_double_cheque = False
                continue
            # Check if this journal is configured for Double Cheques
            config = self.env['bank.double.cheque.config'].search([
                ('journal_ids', 'in', [rec.journal_id.id])
            ], limit=1)
            rec.show_double_cheque = bool(config)

    def action_print_double_check(self):
        configs = self.env['bank.double.cheque.config'].search(
            [('journal_ids', 'in', [self.journal_id.id])]
        )
        if not configs:
            raise UserError("No Bank Double Cheque Configuration is linked to this journal.")
        configs.ensure_one()
        return configs.action_print_double_cheque_for_payment(self)