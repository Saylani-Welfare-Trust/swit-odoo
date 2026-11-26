# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BulkBillDateReferenceWizard(models.TransientModel):
    _name = 'bulk.bill.date.reference.wizard'
    _description = 'Bulk Set Bill Date and Bill Reference'

    invoice_date = fields.Date(
        string='Bill Date',
        help='Leave blank to keep the existing date.')
    ref = fields.Char(
        string='Bill Reference',
        help='Vendor bill number (Odoo field "ref"). '
             'Leave blank to keep the existing reference.')
    set_custom_reference_too = fields.Boolean(
        string='Also copy to Vendor Invoice No. (Finance field)',
        help='If checked, the Bill Reference is also written into the '
             'custom "Vendor Invoice No." field used by Finance matching.')

    move_count = fields.Integer(
        string='Selected Bills',
        compute='_compute_move_count')

    @api.depends_context('active_ids')
    def _compute_move_count(self):
        self.move_count = len(self.env.context.get('active_ids', []))

    @api.constrains('invoice_date', 'ref')
    def _check_at_least_one(self):
        for wiz in self:
            if not wiz.invoice_date and not wiz.ref:
                raise ValidationError(
                    _('Please fill at least one of "Bill Date" or '
                      '"Bill Reference" to update.'))

    def action_apply(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_('No bills were selected.'))

        moves = self.env['account.move'].browse(active_ids)

        # Basic sanity checks
        for move in moves:
            if move.move_type != 'in_invoice':
                raise UserError(_('%s is not a vendor bill.', move.display_name))
            if move.state == 'cancel':
                raise UserError(_('%s is cancelled and cannot be updated.',
                                  move.display_name))

        vals = {}
        if self.invoice_date:
            vals['invoice_date'] = self.invoice_date
        if self.ref:
            vals['ref'] = self.ref
            if self.set_custom_reference_too:
                vals['vendor_invoice_reference'] = self.ref

        moves.write(vals)

        # Audit trail on each bill
        for move in moves:
            changes = []
            if self.invoice_date:
                changes.append(_('Bill Date set to %s', self.invoice_date))
            if self.ref:
                changes.append(_('Bill Reference set to %s', self.ref))
            if changes:
                move.message_post(body='Bulk update: ' + '; '.join(changes))

        return {'type': 'ir.actions.act_window_close'}