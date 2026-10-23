import logging

from odoo import models, fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class APIDonation(models.Model):
    _name = 'api.donation'
    _description = "API Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    import_id = fields.Char('Id', tracking=True)
    name = fields.Char('Name', tracking=True)
    email = fields.Char('Email', tracking=True)
    country = fields.Char('Country', tracking=True)
    remarks = fields.Char('Remarks', tracking=True)
    website = fields.Char('Website', tracking=True)
    referer = fields.Char('Referer', tracking=True)
    created_at = fields.Datetime('Created at', tracking=True)
    dn_number = fields.Char('DN Number', tracking=True)
    phone = fields.Char('Phone', tracking=True)
    cnic = fields.Char('CNIC', tracking=True)
    ip_address = fields.Char('IP Address', tracking=True)
    currency = fields.Char('Currency', tracking=True)
    updated_at = fields.Datetime('Updated at', tracking=True)
    subscription_for_news = fields.Boolean('Subscription For News', tracking=True)
    subscription_for_whatsapp = fields.Boolean('Subscription For Whatsapp', tracking=True)
    subscription_for_sms = fields.Boolean('Subscription For Sms', tracking=True)
    subscription_interval = fields.Char('Subscription Interval', tracking=True)
    qurbani_country = fields.Char('Qurbani Country', tracking=True)
    qurbani_city = fields.Char('Qurbani City', tracking=True)
    qurbani_day = fields.Char('Qurbani Day', tracking=True)
    donor = fields.Char('Donor', tracking=True)
    donation_type = fields.Char('Donation Type', tracking=True)
    donation_from = fields.Char('Donation From', tracking=True)
    response_code = fields.Char('Response Code', tracking=True)
    response_description = fields.Char('Response Description', tracking=True)
    account_source = fields.Char('Account Source', tracking=True)
    is_recurring = fields.Boolean('Is Recurring', tracking=True)
    conversion_rate = fields.Char('Conversion Rate', tracking=True)
    bank_charges = fields.Float('Bank Charges', tracking=True)
    bank_charges_in_text = fields.Char('Bank Charges In Text', tracking=True)
    blinq_notification_number = fields.Char('Blinq Notification Number', tracking=True)
    total_amount = fields.Char('Total Amount', tracking=True)
    total_amount_local = fields.Char('Total Amount (PKR)', tracking=True)
    donation_id = fields.Char('Donation Id', tracking=True)
    invoice_id = fields.Char('Invoice Id', tracking=True)
    transaction_id = fields.Char('Transaction Id', tracking=True)

    donation_item_ids = fields.One2many('api.donation.item', 'api_donation_id', string='Donation Item')
    qurbani_order_line_ids = fields.One2many('api.qurbani.order.line', 'qurbani_order_id', string="Qurbani Order Lines")

    fetch_history_id = fields.Many2one('fetch.history', string="Fetch History", tracking=True)
    donor_id = fields.Many2one('res.partner', string="Donor", tracking=True)
    qurbani = fields.Boolean('Is Qurbani', tracking=True)
    partner_creation_status = fields.Selection([
        ('pending', 'Pending'),
        ('created', 'Created'),
        ('skipped', 'Skipped'),
        ('failed', 'Failed'),
    ], string="Partner Status", default='pending', tracking=True, index=True)
    error_message = fields.Text('Error Message', tracking=True)
    
    journal_status = fields.Selection([
        ('in_entry', 'In Journal Entry'),
        ('partial', 'Partly in Journal Entry'),
        ('not_in_entry', 'Not in Journal Entry'),
    ], string="Accounting", tracking=True, index=True,
        help="Whether the amounts of this donation were included in the journal entry of its fetch.")
    journal_note = fields.Text('Accounting Note', tracking=True)

    def action_create_partners_for_selected(self):
        """Link the selected donations to their donor: the existing contact of
        the person (CNIC, mobile + phone code, else email) or a new Draft profile.
        Donations without mobile and email get the gateway's Default Donor."""
        if not self:
            raise ValidationError(_("No records selected!"))

        Partner = self.env['res.partner']
        Country = self.env['res.country']
        tag_ids = [tag.id for tag in (
            self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False),
            self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False),
        ) if tag]
        default_partner = self.env['gateway.config'].search(
            [('type', '=', 'api'), ('default_partner_id', '!=', False)], limit=1).default_partner_id

        counts = {'created': 0, 'skipped': 0, 'failed': 0}
        partner_cache = {}
        for record in self:
            if record.partner_creation_status not in ('pending', 'failed'):
                continue

            country = Country.search([('code', '=', (record.country or '').strip().upper())], limit=1) \
                if record.country else Country
            mobile = Partner._import_normalize_mobile(record.phone, country or None)
            cnic = Partner._import_normalize_cnic(record.cnic)
            email = (record.email or '').strip()

            if not mobile and not email:
                if default_partner:
                    record.write({'donor_id': default_partner.id, 'partner_creation_status': 'skipped',
                                  'error_message': False})
                    counts['skipped'] += 1
                else:
                    record.write({'partner_creation_status': 'failed', 'error_message': _(
                        'No mobile or email, and no Default Donor on the API gateway configuration.')})
                    counts['failed'] += 1
                continue

            key = (cnic or '', mobile or '', country.id, email.lower())
            if key not in partner_cache:
                partner_cache[key] = Partner._import_find_or_create_partner(
                    record.name, mobile=mobile or '', country=country or None, cnic=cnic or '',
                    email=email, tag_ids=tag_ids)
            partner, error = partner_cache[key]
            if partner:
                record.write({'donor_id': partner.id, 'partner_creation_status': 'created',
                              'error_message': False})
                counts['created'] += 1
            else:
                record.write({'partner_creation_status': 'failed', 'error_message': error})
                counts['failed'] += 1

        message = _('Donations linked to their donor: %(created)s. Default Donor: %(skipped)s. '
                    'Failed: %(failed)s (see Error Message). New donors are Draft profiles.') % counts
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Partner Creation'),
                'message': message,
                'type': 'success' if not counts['failed'] else 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }
