from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]

notification_selection = [
    ('pending', 'Pending'),
    ('sent', 'Sent'),
    ('failed', 'Failed')
]


class Donation(models.Model):
    _name = 'donation'
    _description = "Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donor_id = fields.Many2one('res.partner', string="Donor / Student", tracking=True)
    journal_id = fields.Many2one('account.journal', string="Journal", tracking=True)
    product_id = fields.Many2one('product.product', string="Product", tracking=True)
    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string="Currency")
    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    name = fields.Char('Name', default="New", tracking=True)
    transaction_id = fields.Char('Transaction ID', tracking=True)

    reference = fields.Text('Reference/Remarks', tracking=True)
    
    date = fields.Char('Date', tracking=True, index=True)

    amount = fields.Monetary('Amount', tracking=True)

    is_fee = fields.Boolean('Is Fee', tracking=True)

    state = fields.Selection(selection=state_selection, string="State", default="draft", tracking=True, index=True)
    notification_state = fields.Selection(selection=notification_selection, string="WhatsApp / SMS", copy=False)
    notification_result = fields.Char('WhatsApp / SMS Result', copy=False)

    # ---------- DONATION NOTIFICATION ----------
    def _build_donation_receipt_message(self):
        self.ensure_one()

        return f"""Dear {self.donor_id.name},

Thank you for your donation!

Reference: {self.name}
Transaction ID: {self.transaction_id or '-'}
Amount: {self.amount:,.2f} {self.currency_id.name or 'PKR'}
Purpose: {self.product_id.name or '-'}

May Allah bless you!

- SWIT"""

    def _send_donation_notification(self):
        """Donation receipt to the donor of an imported / online donation:
        WhatsApp first, SMS fallback (bn.donor.notifier of bn_sms_whatsapp)."""
        self.ensure_one()
        if 'bn.donor.notifier' not in self.env:
            return {'status': 'error', 'message': 'The WhatsApp / SMS module is not installed'}
        message = self._build_donation_receipt_message()
        return self.env['bn.donor.notifier']._send(
            self, self.donor_id,
            lambda link: message + (f"\n\nReceipt: {link}" if link else ''),
            report_name='bn_import_donation.donation_form',
            filename=f"Receipt_{self.name.replace('/', '_')}.pdf")

    @api.model
    def _cron_send_donation_notifications(self, limit=30):
        """An import can hold hundreds of donations, so the messages go out
        from this cron instead of the import's Confirm button."""
        donations = self.search([('notification_state', '=', 'pending')], order='id', limit=limit)

        for donation in donations:
            # Taken out of the queue before sending: if the worker dies half
            # way, the donor is never messaged again on the next run.
            donation.write({
                'notification_state': 'failed',
                'notification_result': 'Interrupted while sending',
            })
            self.env.cr.commit()

            try:
                result = donation._send_donation_notification()
                donation.write({
                    'notification_state': 'failed' if result['status'] == 'error' else 'sent',
                    'notification_result': result['message'],
                })
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                _logger.error('Donation %s: notification step failed: %s', donation.name, str(e))

        if self.search_count([('notification_state', '=', 'pending')]):
            self.env.ref('bn_import_donation.send_donation_notification_cron')._trigger()



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('import_donation') or 'New'
        return super().create(vals_list)

    def _check_standalone(self, action):
        for rec in self:
            if rec.import_donation_id:
                raise UserError(_(
                    '"%(donation)s" belongs to the import "%(batch)s": its status follows the import '
                    '(Confirm posts all of its donations).'
                ) % {'donation': rec.display_name, 'batch': rec.import_donation_id.display_name})

    def action_confirm(self):
        self._check_standalone(_('Confirm'))
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('"%s" is already posted.') % rec.display_name)
        self.state = 'posted'

    def action_draft(self):
        self._check_standalone(_('Reset to Draft'))
        for rec in self:
            if rec.state != 'posted':
                raise ValidationError(_('"%s" is already in Draft.') % rec.display_name)
        self.state = 'draft'

    def unlink(self):
        if not self.env.su:
            for rec in self:
                if rec.state == 'posted':
                    raise UserError(_('"%s" is posted and cannot be deleted.') % rec.display_name)
                if rec.import_donation_id:
                    raise UserError(_('Reset the import "%s" to Draft to remove its donations.')
                                    % rec.import_donation_id.display_name)
        return super().unlink()
