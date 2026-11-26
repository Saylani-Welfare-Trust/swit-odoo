# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BulkBillDateReferenceWizard(models.TransientModel):
    _name = 'bulk.bill.date.reference.wizard'
    _description = 'Bulk Set Bill Date and Bill Reference'

    move_ids = fields.Many2many(
        'account.move',
        'bulk_bill_date_ref_wizard_move_rel',
        'wizard_id', 'move_id',
        string='Selected Bills',
    )

    move_count = fields.Integer(
        string='Number of Bills',
        compute='_compute_summary')
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_summary')
    total_amount = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        compute='_compute_summary',
        help='Sum of the selected bills, in company currency.')

    invoice_date = fields.Date(string='Bill Date')
    bill_reference = fields.Char(string='Bill Reference')
    set_custom_reference_too = fields.Boolean(
        string='Also write to Vendor Invoice No. (Finance field)')

    @api.depends('move_ids', 'move_ids.amount_total_signed')
    def _compute_summary(self):
        company_currency = self.env.company.currency_id
        for wiz in self:
            wiz.currency_id = company_currency
            wiz.move_count = len(wiz.move_ids)
            wiz.total_amount = sum(abs(m.amount_total_signed) for m in wiz.move_ids)

    @api.constrains('invoice_date', 'bill_reference')
    def _check_at_least_one(self):
        for wiz in self:
            if not wiz.invoice_date and not wiz.bill_reference:
                raise ValidationError(_(
                    'Please fill at least one of "Bill Date" or '
                    '"Bill Reference" to update.'))

    def action_apply(self):
        moves = self.move_ids
        if not moves:
            raise UserError(_('No bills were selected.'))

        non_draft = moves.filtered(lambda m: m.state != 'draft')
        if non_draft:
            raise UserError(_(
                'This action only applies to draft bills. '
                'The following bills are not draft: %s',
                ', '.join(non_draft.mapped('display_name'))))

        vals = {}
        if self.invoice_date:
            vals['invoice_date'] = self.invoice_date
        if self.bill_reference:
            vals['ref'] = self.bill_reference
            if self.set_custom_reference_too:
                vals['vendor_invoice_reference'] = self.bill_reference

        moves.write(vals)

        for move in moves:
            changes = []
            if self.invoice_date:
                changes.append(_('Bill Date set to %s', self.invoice_date))
            if self.bill_reference:
                changes.append(_('Bill Reference set to %s', self.bill_reference))
            if changes:
                move.message_post(body='Bulk update: ' + '; '.join(changes))

        return {'type': 'ir.actions.act_window_close'}