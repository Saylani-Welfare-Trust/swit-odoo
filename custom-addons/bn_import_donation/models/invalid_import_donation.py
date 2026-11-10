from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import re


class InvalidImportDonation(models.Model):
    _name = 'invalid.import.donation'
    _description = "Invalid Import Donation"


    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    transaction_id = fields.Char('Transaction ID')
    donor_student_name = fields.Char('Donor / Student Name')
    mobile = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)
    email = fields.Char('Email')
    product = fields.Char('Product')
    date = fields.Char('Date')
    amount = fields.Float('Amount')
    reference = fields.Char('Reference')

    reason = fields.Char('Reason')
    is_student = fields.Boolean('Is Student', default=False)
    hide_button = fields.Boolean('Hide Button', default=False)


    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    def action_approve(self):
        """Approve a corrected row: it is checked again like a row of the file.
        Before the upload it becomes a valid line; after the upload its
        donation is created right away."""
        self.ensure_one()
        batch = self.import_donation_id
        batch._check_group('bn_import_donation.import_donation_manager_group', _('Approve'))
        batch._check_state(('validated', 'uploaded', 'sync_donor'), _('Approve'))
        if self.hide_button:
            raise UserError(_('This line has already been processed.'))

        vals = {name: self[name] for name in
                ('transaction_id', 'donor_student_name', 'mobile', 'cnic_no', 'email',
                 'product', 'date', 'amount', 'reference', 'is_student')}
        reason = batch._check_row(vals)
        line = self.env['valid.import.donation']
        if not reason:
            vals['import_donation_id'] = batch.id
            line = line.sudo().create(vals)
            if batch.state in ('uploaded', 'sync_donor'):
                failed = batch._upload_lines(line)
                if failed:
                    reason = failed[0][1]
                    line.unlink()
        if reason:
            self.reason = reason
            # Raising would roll the new reason back: show it on the line instead.
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': _('Not approved'), 'message': reason, 'type': 'warning', 'sticky': False,
                           'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
            }
        self.write({'hide_button': True, 'reason': _('Approved')})
        return True
