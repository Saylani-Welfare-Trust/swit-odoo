# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    finance_confirmed = fields.Boolean(string='Finance Confirmed', copy=False, tracking=True)
    finance_confirmed_by = fields.Many2one('res.users', readonly=True, copy=False)
    finance_confirmed_date = fields.Datetime(readonly=True, copy=False)
    vendor_invoice_reference = fields.Char(
        string='Vendor Invoice No.',
        help='Physical / emailed vendor invoice reference matched by Finance before posting.')
    finance_match_remarks = fields.Text(string='Finance Matching Remarks')

    forwarded_to_treasury = fields.Boolean(string='Forwarded to Treasury', copy=False, tracking=True)
    treasury_forwarded_by = fields.Many2one('res.users', readonly=True, copy=False)
    treasury_forwarded_date = fields.Datetime(readonly=True, copy=False)
    treasury_user_id = fields.Many2one(
        'res.users', string='Assigned Treasury Officer', copy=False,
        help='Optional explicit assignment; if blank, any Treasury group member can act.')

    def action_finance_confirm_and_post(self):
        """Finance matches the draft bill against the physical vendor invoice, then posts it."""
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise ValidationError(_('This action only applies to vendor bills.'))
        if not self.env.user.has_group('bn_procurement_finance.group_finance'):
            raise ValidationError(_('Only Finance users can confirm vendor bills.'))
        if not self.vendor_invoice_reference:
            raise ValidationError(_('Please enter the Vendor Invoice Reference before confirming.'))
        self.write({
            'finance_confirmed': True,
            'finance_confirmed_by': self.env.user.id,
            'finance_confirmed_date': fields.Datetime.now(),
        })
        self.action_post()
        return True

    def action_forward_to_treasury(self):
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise ValidationError(_('This action only applies to vendor bills.'))
        if not self.env.user.has_group('bn_procurement_finance.group_finance'):
            raise ValidationError(_('Only Finance users can forward bills to Treasury.'))
        if not self.finance_confirmed or self.state != 'posted':
            raise ValidationError(_('Bill must be Finance Confirmed and Posted before forwarding to Treasury.'))
        self.write({
            'forwarded_to_treasury': True,
            'treasury_forwarded_by': self.env.user.id,
            'treasury_forwarded_date': fields.Datetime.now(),
        })
        return True
