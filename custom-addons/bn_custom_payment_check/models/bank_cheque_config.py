# -*- coding: utf-8 -*-

from odoo import models, fields


class BankChequeConfig(models.Model):
    _name = 'bank.cheque.config'
    _description = 'Bank Cheque Configuration'
    _order = 'bank_name asc'
    _rec_name = 'bank_name'

    bank_name = fields.Char(
        string='Bank Name',
        required=True,
    )

    journal_ids = fields.Many2many('account.journal', string='Journals', required=True)

    # ==========================================================
    # A/C Payee
    # ==========================================================
    ac_payee_margin_top = fields.Float(
        string='A/C Payee Top Margin (mm)',
        default=16.0,
    )
    ac_payee_margin_left = fields.Float(
        string='A/C Payee Left Margin (mm)',
        default=128.0,
    )
    ac_payee_font_size = fields.Float(
        string='A/C Payee Font Size (pt)',
        default=10.0,
    )

    # ==========================================================
    # DATE
    # ==========================================================
    date_margin_top = fields.Float(
        string='Date Top Margin (mm)',
        default=16.0,
    )
    date_margin_left = fields.Float(
        string='Date Left Margin (mm)',
        default=128.0,
    )
    date_font_size = fields.Float(
        string='Date Font Size (pt)',
        default=10.0,
    )

    # ==========================================================
    # PAYEE
    # ==========================================================
    payee_margin_top = fields.Float(
        string='Payee Top Margin (mm)',
        default=34.0,
    )
    payee_margin_left = fields.Float(
        string='Payee Left Margin (mm)',
        default=18.0,
    )
    payee_font_size = fields.Float(
        string='Payee Font Size (pt)',
        default=10.0,
    )

    # ==========================================================
    # AMOUNT IN WORDS
    # ==========================================================
    words_margin_top = fields.Float(
        string='Amount in Words Top Margin (mm)',
        default=43.0,
    )
    words_margin_left = fields.Float(
        string='Amount in Words Left Margin (mm)',
        default=25.0,
    )
    words_font_size = fields.Float(
        string='Amount in Words Font Size (pt)',
        default=10.0,
    )

    # ==========================================================
    # NUMERIC AMOUNT
    # ==========================================================
    amount_margin_top = fields.Float(
        string='Amount Top Margin (mm)',
        default=38.0,
    )
    amount_margin_left = fields.Float(
        string='Amount Left Margin (mm)',
        default=120.0,
    )
    amount_font_size = fields.Float(
        string='Amount Font Size (pt)',
        default=10.0,
    )

    # ==========================================================
    # CHEQUE
    # ==========================================================
    cheque_margin_top = fields.Float(
        string='Top Margin (mm)',
        default=0.0
    )
    cheque_margin_left = fields.Float(
        string='Left Margin (mm)',
        default=0.0
    )
    cheque_width = fields.Float(
        string='Width (mm)',
        default=0.0
    )
    cheque_height = fields.Float(
        string='Height (mm)',
        default=0.0
    )

    # ==========================================================
    # PREVIEW
    # ==========================================================
    active = fields.Boolean(
        default=True,
    )

    def action_print_cheque_for_payment(self, payment):

        return self.env.ref(
            'bn_custom_payment_check.action_report_dynamic_cheque'
        ).with_context(
            cheque_config_id=self.id,
        ).report_action(payment)