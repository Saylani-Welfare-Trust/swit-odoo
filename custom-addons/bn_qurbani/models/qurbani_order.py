from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re

_logger = logging.getLogger(__name__)


class QurbaniOrder(models.Model):
    _name = 'qurbani.order'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Qurbani POS Orders'

    donor_id = fields.Many2one('res.partner', string="Donor")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    country_code_id = fields.Many2one(related='donor_id.country_code_id', string="Country Code", store=True)

    name = fields.Char('Name', default="New")
    mobile = fields.Char(related='donor_id.mobile', string="Mobile No.", size=10)

    remarks = fields.Text('Remarks')

    amount = fields.Monetary('Amount', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')

    qurbani_order_line_ids = fields.One2many('qurbani.order.line', 'qurbani_order_id', string="Qurbani Order Lines")
    pos_qurbani_order = fields.Boolean('POS Qurbani Order', default=True)
    
    # API/Web Order Fields
    api_response_id = fields.Char('API Response ID', help="Unique ID from API response")
    donation_type = fields.Char('Donation Type', help="Type of donation (e.g., standard)")
    donation_from = fields.Char('Donation From', help="Source of donation (e.g., web, pos)")
    dn_number = fields.Char('DN Number', help="Donation Number from API")
    bank_charges = fields.Monetary('Bank Charges', currency_field='currency_id', help="Bank charges from transaction")
    transaction_id = fields.Char('Transaction ID', help="Payment transaction ID")
    api_currency = fields.Char('API Currency', help="Original currency from API")
    api_created_at = fields.Datetime('API Created At', help="Creation timestamp from API")
    api_updated_at = fields.Datetime('API Updated At', help="Update timestamp from API")
    donor_phone = fields.Char('Donor Phone', help="Original phone from API")
    donor_email = fields.Char('Donor Email', help="Original email from API")
    donor_cnic = fields.Char('Donor CNIC', help="Original CNIC from API")
    donor_country = fields.Char('Donor Country', help="Original country from API")
    donor_ip_address = fields.Char('Donor IP Address', help="IP address from API")
    subscription_news = fields.Boolean('Subscription for News', default=False)
    subscription_whatsapp = fields.Boolean('Subscription for WhatsApp', default=False)
    subscription_sms = fields.Boolean('Subscription for SMS', default=False)
    
    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_order') or ('New')

        return super(QurbaniOrder, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.qurbani_order_line_ids)
    
    @api.model
    def create_web_qurbani_order(self, api_data):
        """
        Create a Qurbani Order from API/Web response data.
        
        Args:
            api_data: Dict with API response data containing:
                - items: List of order items
                - donor_details: Dict with donor information
                - total_amount: Total amount
                - remarks: Optional remarks
                - currency: Currency code
                - All other API fields
        
        Returns:
            Dict with status, qurbani_order_id, and name
        """
        try:
            # Extract donor details
            donor_details = api_data.get('donor_details', {})
            donor_name = donor_details.get('name', 'Web Donor')
            donor_phone = donor_details.get('phone', '')
            donor_email = donor_details.get('email', '')
            donor_country = donor_details.get('country', '')
            donor_cnic = donor_details.get('cnic', '')
            
            # Extract last 10 digits of phone for mobile field
            mobile = donor_phone[-10:] if donor_phone and len(donor_phone) >= 10 else donor_phone
            
            # Find or create donor based on phone and country
            donor_id = None
            if mobile and donor_country:
                # Find country
                country = self.env['res.country'].search([('code', '=', donor_country)], limit=1)
                country_code_id = country.id if country else None
                
                # Search for existing donor
                existing_donor = self.env['res.partner'].search([
                    ('mobile', '=', mobile),
                    ('country_code_id', '=', country_code_id) if country_code_id else ('country_code_id', '=', None)
                ], limit=1)
                
                if existing_donor:
                    donor_id = existing_donor.id
                else:
                    # Create new donor
                    donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
                    individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
                    
                    category_ids = []
                    if donor_category:
                        category_ids.append(donor_category.id)
                    if individual_category:
                        category_ids.append(individual_category.id)
                    
                    new_donor = self.env['res.partner'].create({
                        'name': donor_name,
                        'mobile': mobile,
                        'email': donor_email,
                        'country_code_id': country_code_id,
                        'category_id': [(6, 0, category_ids)] if category_ids else [],
                    })
                    donor_id = new_donor.id
                    # Register the partner
                    if hasattr(new_donor, 'action_register'):
                        new_donor.action_register()
            
            # Get or create default donor if no phone provided
            if not donor_id:
                default_donor = self.env['res.partner'].search(
                    [('name', 'ilike', 'Web Donor')], 
                    limit=1
                )
                if default_donor:
                    donor_id = default_donor.id
                else:
                    # Create a generic web donor
                    web_donor = self.env['res.partner'].create({
                        'name': donor_name or 'Web Donor',
                        'email': donor_email,
                    })
                    donor_id = web_donor.id
            
            # Get Hijri (current year)
            hijri = self.env['hijri'].search([], order="id desc", limit=1)
            if not hijri:
                return {
                    "status": "error",
                    "message": "No Hijri record found. Please create a Hijri record first."
                }
            
            # Get currency
            currency_code = api_data.get('currency', 'USD')
            currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            if not currency:
                currency = self.env.company.currency_id
            
            # Prepare order lines
            order_lines = []
            total_line_amount = 0.0
            
            for item in api_data.get('items', []):
                # Extract item information
                item_name = ''
                type_name = ''
                
                item_data = item.get('item', {})
                if isinstance(item_data, dict) and 'en' in item_data:
                    item_name = item_data.get('en', {}).get('name', '')
                
                type_data = item.get('type', {})
                if isinstance(type_data, dict) and 'en' in type_data:
                    type_name = type_data.get('en', {}).get('name', '')
                
                # Find product by name (case-insensitive)
                product = self.env['product.product'].search([
                    ('name', 'ilike', "Qurbani Web"),
                    ('categ_id.name', 'ilike', 'qurbani')
                ], limit=1)
                
                if not product:
                    # Try searching without category filter
                    product = self.env['product.product'].search([
                        ('name', 'ilike', "Qurbani Web")
                    ], limit=1)
                
                if not product:
                    _logger.warning(f"Product not found for item: {item_name}")
                    continue
                
                quantity = int(item.get('qty', 1))
                amount = float(item.get('price', 0))
                
                # Find day
                day_name = item.get('day', '')
                day = self.env['qurbani.day'].search([('name', 'ilike', day_name)], limit=1)
                
                # Find city/location if available
                city_name = api_data.get('donor_details', {}).get('qurbaniCity', '')
                city = self.env['stock.location'].search([
                    ('name', 'ilike', city_name),
                    ('usage', '=', 'internal')
                ], limit=1)
                
                # Get share names list
                share_names = item.get('share_names', [donor_name])
                if not share_names or share_names == []:
                    share_names = [donor_name]
                
                # Loop through quantity and create individual lines
                for idx in range(quantity):
                    # Get the share name for this hissa (cycle through if needed)
                    share_name = share_names[idx % len(share_names)] if share_names else donor_name
                    
                    # Create hissa_name with numbering
                    hissa_name = f"{idx + 1}. {share_name}" if quantity > 1 else share_name
                    
                    order_lines.append((0, 0, {
                        'product_id': product.id,
                        'quantity': 1,  # Each line has quantity 1
                        'amount': amount,
                        'day_id': day.id if day else False,
                        'hijri_id': hijri.id,
                        'city_id': city.id if city else False,
                        'hissa_name': hissa_name,
                    }))
            
            
            # Create the qurbani order
            qurbani_order = self.env['qurbani.order'].create({
                'donor_id': donor_id,
                'currency_id': currency.id,
                'remarks': api_data.get('remarks', ''),
                'total_amount': float(api_data.get('total_amount', 0)),
                'qurbani_order_line_ids': order_lines,
                'pos_qurbani_order': False,  # Mark as web order, not POS
                
                # Store API response data
                'api_response_id': api_data.get('_id', ''),
                'donation_type': api_data.get('donation_type', ''),
                'donation_from': api_data.get('donation_from', 'web'),
                'dn_number': api_data.get('DN_Number', ''),
                'bank_charges': float(api_data.get('bank_charges', 0)),
                'transaction_id': api_data.get('transaction_id', ''),
                'api_currency': currency_code,
                'api_created_at': self._parse_iso_datetime(api_data.get('createdAt')),
                'api_updated_at': self._parse_iso_datetime(api_data.get('updatedAt')),
                'donor_phone': donor_phone,
                'donor_email': donor_email,
                'donor_cnic': donor_cnic,
                'donor_country': donor_country,
                'donor_ip_address': donor_details.get('ipAddress', ''),
                'subscription_news': donor_details.get('subscriptionForNews', False),
                'subscription_whatsapp': donor_details.get('subscriptionForWhatsapp', False),
                'subscription_sms': donor_details.get('subscriptionForSms', False),
            })
            
            # Calculate the total amount
            qurbani_order.calculate_amount()
            
            return {
                "status": "success",
                "qurbani_order_id": qurbani_order.id,
                "name": qurbani_order.name,
                "message": f"Web Qurbani Order created successfully"
            }
        
        except Exception as e:
            _logger.error(f"Error creating web qurbani order: {str(e)}")
            return {
                "status": "error",
                "message": f"Error creating order: {str(e)}"
            }
    
    @staticmethod
    def _parse_iso_datetime(iso_string):
        """Parse ISO 8601 datetime string to Odoo datetime format"""
        if not iso_string:
            return None
        try:
            from datetime import datetime
            # Parse ISO 8601 format (e.g., '2026-05-04T20:01:19.593Z')
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)
        except Exception as e:
            _logger.warning(f"Could not parse datetime {iso_string}: {str(e)}")
            return None
    
    def action_show_pos_order(self):
        self.ensure_one()

        pos_order = self.env['pos.order'].search([
            ('source_document', '=', self.name)
        ], limit=1)

        if not pos_order:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Not Found',
                    'message': 'No POS Order found for this Qurbani Order.',
                    'type': 'warning',
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order',
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': pos_order.id,
            'target': 'current',
        }

    @api.model
    def create_qurbani_record(self, data):

        schedule_usage = {}
        demand_cache = {}

        Hijri = self.env['hijri'].search([], order="id desc", limit=1)
        if not Hijri:
            return {"status": "error", "body": "No Hijri found"}

        # ==================================================
        # 1. HISSA RULE
        # ==================================================
        def _get_divisor(demand):
            name = (demand.inventory_product_id.name or "").lower()

            if "cow" in name:
                return 7
            elif "goat" in name:
                return 1
            return 1

        # ==================================================
        # 2. GET DEMAND
        # ==================================================
        def _get_demand(line):

            schedule = line.get('qurbani_schedule', {})
            slot = schedule.get('slot', {})

            key = (
                line['product_id'],
                slot.get('distribution', {}).get('location'),
            )

            if key in demand_cache:
                return demand_cache[key]

            distribution = self.env['distribution.schedule'].search([
                ('pos_product_ids', 'in', line['product_id']),
                ('location_id', '=', slot.get('distribution', {}).get('location')),
                ('hijri_id', '=', Hijri.id),
            ], limit=1)

            if not distribution or not distribution.slaughter_schedule_id:
                demand_cache[key] = False
                return False

            slaughter = distribution.slaughter_schedule_id

            demand = self.env['qurbani.slaughter.slot.demand'].search([
                ('day_id', '=', distribution.day_id.id),
                ('hijri_id', '=', distribution.hijri_id.id),
                ('slaughter_location_id', '=', distribution.slaughter_location_id.id),
                ('inventory_product_id', '=', distribution.inventory_product_id.id),
                ('start_time', '<=', slot.get('slaughter', {}).get('start') or slaughter.start_time),
                ('end_time', '>=', slot.get('slaughter', {}).get('end') or slaughter.end_time),
            ], limit=1)

            demand_cache[key] = demand
            return demand

        # ==================================================
        # 3. GROUP (ONLY HISSA COUNT)
        # ==================================================
        for line in data['order_lines']:
            product = self.env['product.product'].browse(line['product_id'])

            # ❌ Skip non-qurbani products
            if 'qurbani' not in product.categ_id.name.lower():
                continue

            demand = _get_demand(line)
            if not demand:
                continue

            qty = int(line.get('quantity', 0))  # this is HISSA

            if demand.id not in schedule_usage:
                schedule_usage[demand.id] = {
                    'demand': demand,
                    'qty': 0
                }

            schedule_usage[demand.id]['qty'] += qty

        # ==================================================
        # 4. VALIDATION
        # ==================================================
        for usage in schedule_usage.values():

            demand = usage['demand']
            qty = usage['qty']

            available = demand.remaining_hissa
            # available = (demand.total_hissa or 0) - (demand.current_hissa or 0)

            if qty > available:
                return {
                    "status": "error",
                    "body": (
                        f"Not enough Hissa for Demand {demand.id}. "
                        f"Available: {available}, Requested: {qty}"
                    ),
                }

        # ==================================================
        # 5. APPLY UPDATES (🔥 CORRECT INVENTORY-STYLE LOGIC)
        # ==================================================
        for usage in schedule_usage.values():

            demand = usage['demand']
            incoming_hissa = usage['qty']

            divisor = _get_divisor(demand)

            old_current = demand.current_hissa or 0

            # STEP 1: add hissa
            total_hissa = old_current + incoming_hissa

            # STEP 2: detect completed animals
            completed_animals = int(total_hissa // divisor)

            # STEP 3: remaining hissa after full animals
            remaining_hissa = total_hissa % divisor

            # STEP 4: reduce remaining demand
            new_remaining_demand = max(
                (demand.remaining_demand or 0) - completed_animals,
                0
            )

            demand.write({
                'current_hissa': remaining_hissa,   # 🔥 leftover like inventory
                'booked_hissa': (demand.booked_hissa or 0) + incoming_hissa,
                'remaining_demand': new_remaining_demand,
            })

        # ==================================================
        # 6. CREATE ORDER LINES
        # ==================================================
        product_lines = []

        for line in data['order_lines']:
            product = self.env['product.product'].browse(line['product_id'])

            # ❌ Skip non-qurbani products
            if 'qurbani' not in product.categ_id.name.lower():
                continue

            schedule = line.get('qurbani_schedule', {})
            slot = schedule.get('slot', {})

            product_lines.append((0, 0, {
                'product_id': line.get('product_id'),
                'quantity': line.get('quantity'),
                'amount': line.get('price'),

                'day_id': self.env['qurbani.day'].search([
                    ('name', '=', slot.get('day'))
                ], limit=1).id,

                'hijri_id': Hijri.id,

                'city_id': self.env['stock.location'].search([
                    ('name', '=', schedule.get('city'))
                ], limit=1).id,

                'distribution_id': self.env['stock.location'].browse(slot.get('distribution', {}).get('location')).id,

                'hissa_name': schedule.get('name', ''),
                'start_time': slot.get('distribution', {}).get('start'),
                'end_time': slot.get('distribution', {}).get('end'),
            }))

        # ==================================================
        # 7. CREATE ORDER
        # ==================================================
        qurbani = self.env['qurbani.order'].create({
            'donor_id': data['donor_id'],
            'qurbani_order_line_ids': product_lines,
        })

        qurbani.calculate_amount()

        return {
            "status": "success",
            "id": qurbani.id,
            "name": qurbani.name,
        }