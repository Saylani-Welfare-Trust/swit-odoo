from odoo import models, fields


class APIDonation(models.Model):
    _name = 'api.donation'
    _description = "API Donation"


    import_id = fields.Char('Id')
    name = fields.Char('Name')
    email = fields.Char('Email')
    country = fields.Char('Country')
    remarks = fields.Char('Remarks')
    website = fields.Char('Website')
    referer = fields.Char('Referer')
    created_at = fields.Datetime('Created at')
    dn_number = fields.Char('DN Number')
    phone = fields.Char('Phone')
    cnic = fields.Char('CNIC')
    ip_address = fields.Char('IP Address')
    currency = fields.Char('Currency')
    updated_at = fields.Datetime('Updated at')
    subscription_for_news = fields.Boolean('Subscription For News')
    subscription_for_whatsapp = fields.Boolean('Subscription For Whatsapp')
    subscription_for_sms = fields.Boolean('Subscription For Sms')
    subscription_interval = fields.Char('Subscription Interval')
    qurbani_country = fields.Char('Qurbani Country')
    qurbani_city = fields.Char('Qurbani City')
    qurbani_day = fields.Char('Qurbani Day')
    donor = fields.Char('Donor')
    donation_type = fields.Char('Donation Type')
    donation_from = fields.Char('Donation From')
    response_code = fields.Char('Response Code')
    response_description = fields.Char('Response Description')
    account_source = fields.Char('Account Source')
    is_recurring = fields.Boolean('Is Recurring')
    conversion_rate = fields.Char('Conversion Rate')
    bank_charges = fields.Float('Bank Charges')
    bank_charges_in_text = fields.Char('Bank Charges In Text')
    blinq_notification_number = fields.Char('Blinq Notification Number')
    total_amount = fields.Char('Total Amount')
    total_amount_local = fields.Char('Total Amount (PKR)')
    donation_id = fields.Char('Donation Id')
    invoice_id = fields.Char('Invoice Id')
    transaction_id = fields.Char('Transaction Id')

    donation_item_ids = fields.One2many('api.donation.item', 'api_donation_id', string='Donation Item')

    fetch_history_id = fields.Many2one('fetch.history', string="Fetch History")
    donor_id = fields.Many2one('res.partner', string="Donor")