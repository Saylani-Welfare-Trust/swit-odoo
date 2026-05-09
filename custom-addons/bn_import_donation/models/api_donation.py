from odoo import models, fields


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

    fetch_history_id = fields.Many2one('fetch.history', string="Fetch History", tracking=True)
    donor_id = fields.Many2one('res.partner', string="Donor", tracking=True)