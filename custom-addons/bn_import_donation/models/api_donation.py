from odoo import models, fields
from odoo.exceptions import ValidationError


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
    ], string="Partner Status", default='pending', tracking=True)
    
    def action_create_partners_for_selected(self):
        """Create partners for selected donation records - Partners stay in DRAFT state"""
        if not self:
            raise ValidationError(_("No records selected!"))
        
        Partner = self.env['res.partner']
        Country = self.env['res.country']
        
        # Get category IDs
        donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
        individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
        
        category_ids = []
        if donor_category:
            category_ids.append(donor_category.id)
        if individual_category:
            category_ids.append(individual_category.id)
        
        # Default partner for records without donor info
        default_partner = Partner.search(
            [('primary_registration_id', '=', '2025-9999998-9')], 
            limit=1
        )
        default_partner_id = default_partner.id if default_partner else False
        
        # Collect unique donors from selected records
        unique_donors = {}
        
        for record in self:
            if record.partner_creation_status != 'pending':
                continue  # Skip already processed records
            
            if not record.phone and not record.email:
                # No donor info, assign default partner
                if default_partner_id:
                    record.write({
                        'donor_id': default_partner_id,
                        'partner_creation_status': 'skipped',
                    })
                else:
                    record.write({
                        'partner_creation_status': 'failed',
                        'error_message': 'No donor contact info and no default partner configured'
                    })
                continue
            
            mobile = record.phone[-10:] if record.phone else ''
            
            # Find country
            country_code = record.country or ''
            country = Country.search([('code', '=', country_code)], limit=1)
            
            # Create unique key
            key = (mobile, country.id if country else False)
            
            if key not in unique_donors:
                unique_donors[key] = {
                    'name': record.name or f'Donor {mobile}',
                    'mobile': mobile,
                    'email': record.email,
                    'cnic': record.cnic,
                    'country_id': country.id if country else False,
                    'records': []
                }
            
            unique_donors[key]['records'].append(record.id)
        
        # Process each unique donor
        created_count = 0
        skipped_count = 0
        failed_count = 0
        partner_mapping = {}
        failed_keys = []
        
        for key, donor_data in unique_donors.items():
            try:
                mobile, country_id = key
                
                # Check if partner already exists
                existing_partner = Partner.search([
                    '|',
                    ('email', '=', donor_data['email']),
                    ('mobile', '=', donor_data['mobile']),
                ], limit=1)
                
                if existing_partner:
                    # Check if it's a donor
                    is_donor = donor_category and donor_category.id in existing_partner.category_id.ids
                    if not is_donor and category_ids:
                        # Add donor categories (without changing state)
                        existing_partner.write({
                            'category_id': [(4, cat_id) for cat_id in category_ids if cat_id]
                        })
                    
                    partner_mapping[key] = existing_partner.id
                    skipped_count += 1
                    
                else:
                    # Create new partner - STAYS IN DRAFT STATE
                    # Make sure the partner model has a 'state' field and 'draft' is a valid value
                    partner_vals = {
                        'name': donor_data['name'],
                        'mobile': donor_data['mobile'],
                        'email': donor_data['email'],
                        'cnic_no': donor_data['cnic'],
                        'country_code_id': donor_data['country_id'],
                        'category_id': [(6, 0, [cat_id for cat_id in category_ids if cat_id])],
                    }
                    
                    # If your partner model has a state field, explicitly set to draft
                    if hasattr(Partner, 'state'):
                        partner_vals['state'] = 'draft'  # Explicitly set to draft
                    
                    new_partner = Partner.create(partner_vals)
                    
                    # DO NOT call action_register() - Partner stays in draft
                    
                    partner_mapping[key] = new_partner.id
                    created_count += 1
                    
            except Exception as e:
                failed_count += 1
                failed_keys.append(key)
                error_msg = str(e)
                _logger.error(f"Failed to create partner for key {key}: {error_msg}")
                continue
        
        # Update donation records with partner IDs
        records_updated = 0
        
        for key, donor_data in unique_donors.items():
            partner_id = partner_mapping.get(key)
            
            if partner_id:
                for record_id in donor_data['records']:
                    self.browse(record_id).write({
                        'donor_id': partner_id,
                        'partner_creation_status': 'created',
                    })
                    records_updated += 1
                    
            elif key in failed_keys:
                for record_id in donor_data['records']:
                    self.browse(record_id).write({
                        'partner_creation_status': 'failed',
                        'error_message': 'Failed to create partner during batch processing'
                    })
        
        # Show result message
        message = f"""
        Partner Creation Complete:
        - New Partners Created (Draft): {created_count}
        - Already Existed: {skipped_count}
        - Failed: {failed_count}
        - Records Updated: {records_updated}
        
        Note: New partners are in Draft state.
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Partner Creation',
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': True,
            }
        }
