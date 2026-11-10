# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountPaymentTermLine(models.Model):
    _inherit = 'account.payment.term.line'

    # Odoo's own term lines only say "x % after n days of the bill" - nothing tells
    # an installment paid before delivery apart from one due at the bill date.
    milestone_type = fields.Selection([
        ('advance', 'Advance Payment'),
        ('delivery', 'Payment on Delivery'),
        ('credit', 'After Delivery / Credit'),
    ], string='Payment Milestone',
        help='What this installment stands for on a Purchase Order. An "Advance Payment" line '
             'creates a draft vendor payment for its share as soon as the Purchase Order is confirmed.')
