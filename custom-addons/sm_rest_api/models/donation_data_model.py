from odoo import api, fields, models, _


class DonationDataModel(models.Model):
    _name = 'donation.data'
    _description = 'Donation Data'
    _rec_name = 'name'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Donor',
        help='The donor who made this donation',
        domain=[('is_donee', '=', False), ('registration_category', '=', 'donor')]
    )
    import_id = fields.Char(string='Id', tracking=True)
    name = fields.Char(string='Name', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    country = fields.Char(string='Country', tracking=True)
    remarks = fields.Char(string='Remarks', tracking=True)
    website = fields.Char(string='Website', tracking=True)
    referer = fields.Char(string='Referer', tracking=True)
    created_at = fields.Datetime(string='Created at', tracking=True)
    dn_number = fields.Char(string='DN Number', tracking=True)
    phone = fields.Char(string='Phone', tracking=True)
    cnic = fields.Char(string='CNIC', tracking=True)
    ip_address = fields.Char(string='IP Address', tracking=True)
    status = fields.Selection(selection=[('draft', 'Draft'), ('pending', 'Pending'), ('success', 'Success')], string='Status', tracking=True)
    currency = fields.Char(string='Currency', tracking=True)
    updated_at = fields.Datetime(string='Updated at', tracking=True)
    subscription_for_news = fields.Boolean(string='Subscription For News', tracking=True)
    subscription_for_whatsapp = fields.Boolean(string='Subscription For Whatsapp', tracking=True)
    subscription_for_sms = fields.Boolean(string='Subscription For Sms', tracking=True)
    subscription_interval = fields.Char(string='Subscription Interval', tracking=True)
    qurbani_country = fields.Char(string='Qurbani Country', tracking=True)
    qurbani_city = fields.Char(string='Qurbani City', tracking=True)
    qurbani_day = fields.Char(string='Qurbani Day', tracking=True)
    donor = fields.Char(string='Donor', tracking=True)
    donation_type = fields.Char(string='Donation Type', tracking=True)
    donation_from = fields.Char(string='Donation From', tracking=True)
    response_code = fields.Char(string='Response Code', tracking=True)
    response_description = fields.Char(string='Response Description', tracking=True)
    account_source = fields.Char(string='Account Source', tracking=True)
    is_recurring = fields.Boolean(string='Is Recurring', tracking=True)
    conversion_rate = fields.Char(string='Conversion Rate', tracking=True)
    bank_charges = fields.Float(string='Bank Charges', tracking=True)
    bank_charges_in_text = fields.Char(string='Bank Charges In Text', tracking=True)
    blinq_notification_number = fields.Char(string='Blinq Notification Number', tracking=True)
    total_amount = fields.Char(string='Total Amount', tracking=True)
    total_amount_local = fields.Char(string='Total Amount (PKR)', tracking=True)
    donation_id = fields.Char(string='Donation Id', tracking=True)
    invoice_id = fields.Char(string='Invoice Id', tracking=True)
    transaction_id = fields.Char(string='Transaction Id', tracking=True)
    donation_item_ids = fields.One2many(comodel_name='donation.item', inverse_name='donation_data_id', string='Donation Item')

    journal_entry_id = fields.Many2one('account.move', string="Journal Entry")