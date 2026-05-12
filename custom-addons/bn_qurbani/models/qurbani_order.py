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
    country_code_id = fields.Many2one(related='donor_id.country_code_id', string="Country Code", store=True, readonly=True)

    name = fields.Char('Name', default="New")
    mobile = fields.Char(related='donor_id.mobile', string="Mobile No.", size=10)

    remarks = fields.Text('Remarks')

    amount = fields.Monetary('Amount', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')

    # POS vs Web Order indicator
    pos_qurbani_order = fields.Boolean('POS Order', default=True)

    # API/Web Order Fields
    api_response_id = fields.Char('API Response ID')
    donation_type = fields.Char('Donation Type')
    donation_from = fields.Char('Donation From')
    dn_number = fields.Char('DN Number')
    transaction_id = fields.Char('Transaction ID')
    api_currency = fields.Char('API Currency')
    bank_charges = fields.Monetary('Bank Charges', currency_field='currency_id')
    api_created_at = fields.Datetime('API Created At')
    api_updated_at = fields.Datetime('API Updated At')

    # Donor Details
    donor_phone = fields.Char('Donor Phone')
    donor_email = fields.Char('Donor Email')
    donor_cnic = fields.Char('Donor CNIC')
    donor_country = fields.Char('Donor Country')
    donor_ip_address = fields.Char('Donor IP Address')

    # Subscription Preferences
    subscription_news = fields.Boolean('Subscribe to News')
    subscription_whatsapp = fields.Boolean('Subscribe to WhatsApp')
    subscription_sms = fields.Boolean('Subscribe to SMS')

    qurbani_order_line_ids = fields.One2many('qurbani.order.line', 'qurbani_order_id', string="Qurbani Order Lines")


    # @api.constrains('mobile')
    # def _check_mobile_number(self):
    #     for rec in self:
    #         if rec.mobile:
    #             if not re.fullmatch(r"\d{10}", rec.mobile):
    #                 raise ValidationError(
    #                     "Mobile number must contain exactly 10 digits."
    #                 )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_order') or ('New')

        return super(QurbaniOrder, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.qurbani_order_line_ids)
    
    def create_web_qurbani_order(self, donation_record):
        """
        Create Qurbani Order directly from api.donation record
        """

        try:
            order_lines = []

            # Handle qurbani_order_line_ids - can be list of IDs or objects
            qurbani_line_ids = donation_record.get('qurbani_order_line_ids', [])
            
            if qurbani_line_ids:
                # If it's a list of IDs, fetch the actual line objects
                if isinstance(qurbani_line_ids, list) and qurbani_line_ids:
                    if isinstance(qurbani_line_ids[0], int):
                        # It's a list of IDs, fetch from api.qurbani.order.line
                        qurbani_lines = self.env['api.qurbani.order.line'].browse(qurbani_line_ids).exists()
                    else:
                        qurbani_lines = qurbani_line_ids
                else:
                    qurbani_lines = qurbani_line_ids if isinstance(qurbani_line_ids, list) else [qurbani_line_ids]

                # Create lines from qurbani_order_line_ids
                for line in qurbani_lines:
                    if not line.exists():
                        continue
                    
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id if hasattr(line, 'product_id') and line.product_id else False,
                        'quantity': line.quantity if hasattr(line, 'quantity') else 1,
                        'amount': line.amount if hasattr(line, 'amount') else 0.0,
                        'day_id': line.day_id.id if hasattr(line, 'day_id') and line.day_id else False,
                        'hijri_id': line.hijri_id.id if hasattr(line, 'hijri_id') and line.hijri_id else False,
                        'city_id': line.city_id.id if hasattr(line, 'city_id') and line.city_id else False,
                        'hissa_name': line.hissa_name if hasattr(line, 'hissa_name') else '',
                    }))

            # Get donor_id - can be tuple (id, name) or just id - VALIDATE IT EXISTS
            donor_id = donation_record.get('donor_id')
            if isinstance(donor_id, tuple):
                donor_id = donor_id[0]
            
            # Validate donor exists if provided
            if donor_id and isinstance(donor_id, int):
                donor_check = self.env['res.partner'].browse(donor_id).exists()
                if not donor_check:
                    _logger.warning(f"Donor ID {donor_id} does not exist, setting to False")
                    donor_id = False

            # Get currency - VALIDATE IT EXISTS
            currency_name = donation_record.get('currency', 'USD')
            currency_id = self.env['res.currency'].search(
                [('name', '=', currency_name)],
                limit=1
            )
            if not currency_id:
                _logger.warning(f"Currency {currency_name} not found, using company currency")
                currency_id = self.env.company.currency_id
            
            currency_id = currency_id.id if currency_id else self.env.company.currency_id.id

            qurbani_order = self.env['qurbani.order'].create({
                'donor_id': donor_id or False,
                'currency_id': currency_id,
                'remarks': donation_record.get('remarks', ''),
                'total_amount': float(donation_record.get('total_amount', 0.0)),
                'qurbani_order_line_ids': order_lines,
                'pos_qurbani_order': False,

                # API / Donation Fields
                'api_response_id': donation_record.get('import_id', ''),
                'donation_type': donation_record.get('donation_type', ''),
                'donation_from': donation_record.get('donation_from', ''),
                'dn_number': donation_record.get('dn_number', ''),
                'bank_charges': float(donation_record.get('bank_charges', 0.0)),
                'transaction_id': donation_record.get('transaction_id', ''),
                'api_currency': donation_record.get('currency', ''),
                'api_created_at': donation_record.get('created_at'),
                'api_updated_at': donation_record.get('updated_at'),

                # Donor Details
                'donor_phone': donation_record.get('phone', ''),
                'donor_email': donation_record.get('email', ''),
                'donor_cnic': donation_record.get('cnic', ''),
                'donor_country': donation_record.get('country', ''),
                'donor_ip_address': donation_record.get('ip_address', ''),

                # Subscriptions
                'subscription_news': bool(donation_record.get('subscription_for_news', False)),
                'subscription_whatsapp': bool(donation_record.get('subscription_for_whatsapp', False)),
                'subscription_sms': bool(donation_record.get('subscription_for_sms', False)),
            })

            return {
                "status": "success",
                "qurbani_order_id": qurbani_order.id,
                "name": qurbani_order.name,
                "message": "Web Qurbani Order created successfully"
            }

        except Exception as e:
            _logger.error(f"Error creating web qurbani order: {str(e)}", exc_info=True)

            return {
                "status": "error",
                "message": str(e)
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
        # 2. GET DEMAND USING slot_demand_id
        # ==================================================
        def _get_demand(line):

            schedule = line.get('qurbani_schedule', {})
            slot = schedule.get('slot', {})

            slot_demand_id = slot.get('slot_demand_id')

            if not slot_demand_id:
                return False

            if slot_demand_id in demand_cache:
                return demand_cache[slot_demand_id]

            demand = self.env['qurbani.slaughter.slot.demand'].browse(
                slot_demand_id
            ).exists()

            demand_cache[slot_demand_id] = demand

            return demand

        # ==================================================
        # 3. GROUP (ONLY HISSA COUNT)
        # ==================================================
        for line in data.get('order_lines', []):

            product = self.env['product.product'].browse(line['product_id'])

            # ❌ Skip non-qurbani products
            if 'qurbani' not in (product.categ_id.name or '').lower():
                continue

            demand = _get_demand(line)

            if not demand:
                return {
                    "status": "error",
                    "body": "Invalid slaughter slot selected."
                }

            qty = int(line.get('quantity', 0))

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

            if qty > available:
                return {
                    "status": "error",
                    "body": (
                        f"Not enough Hissa for Demand {demand.id}. "
                        f"Available: {available}, Requested: {qty}"
                    ),
                }

        # ==================================================
        # 5. APPLY UPDATES
        # ==================================================
        for usage in schedule_usage.values():

            demand = usage['demand']
            incoming_hissa = usage['qty']

            divisor = _get_divisor(demand)

            old_current = demand.current_hissa or 0

            # STEP 1: ADD HISSA
            total_hissa = old_current + incoming_hissa

            # STEP 2: COMPLETED ANIMALS
            completed_animals = int(total_hissa // divisor)

            # STEP 3: REMAINING HISSA
            remaining_hissa = total_hissa % divisor

            # STEP 4: REMAINING DEMAND
            new_remaining_demand = max(
                (demand.remaining_demand or 0) - completed_animals,
                0
            )

            demand.write({
                'current_hissa': remaining_hissa,
                'booked_hissa': (demand.booked_hissa or 0) + incoming_hissa,
                'remaining_demand': new_remaining_demand,
            })

        # ==================================================
        # 6. CREATE ORDER LINES
        # ==================================================
        product_lines = []

        for line in data.get('order_lines', []):

            product = self.env['product.product'].browse(line['product_id'])

            # ❌ Skip non-qurbani products
            if 'qurbani' not in (product.categ_id.name or '').lower():
                continue

            schedule = line.get('qurbani_schedule', {})
            slot = schedule.get('slot', {})

            demand = _get_demand(line)

            if not demand:
                continue

            slaughter_data = slot.get('slaughter', {})
            distribution_data = slot.get('distribution', {})

            # ==================================================
            # GET CITY
            # ==================================================
            city_id = False

            if demand.slaughter_location_id:
                city_id = (
                    demand.slaughter_location_id.location_id.id
                    if hasattr(demand.slaughter_location_id, 'location_id')
                    else False
                )

            # fallback from schedule city
            if not city_id and schedule.get('city'):
                city = self.env['stock.location'].search([
                    ('name', '=', schedule.get('city'))
                ], limit=1)

                city_id = city.id if city else False

            # ==================================================
            # BUILD LINE
            # ==================================================
            vals = {
                'product_id': line.get('product_id'),
                'quantity': line.get('quantity'),
                'amount': line.get('price'),

                'day_id': demand.day_id.id,
                'hijri_id': demand.hijri_id.id,

                'city_id': city_id,

                'distribution_id': distribution_data.get('location'),

                'slaughter_id': slaughter_data.get('location'),

                'hissa_name': schedule.get('name', ''),

                # DISTRIBUTION TIMES
                'start_time': distribution_data.get('start'),
                'end_time': distribution_data.get('end'),

                # SLAUGHTER TIMES
                'slaughter_start_time': slaughter_data.get('start'),
                'slaughter_end_time': slaughter_data.get('end'),
            }

            product_lines.append((0, 0, vals))

        # ==================================================
        # 7. CREATE ORDER
        # ==================================================
        qurbani = self.env['qurbani.order'].create({
            'donor_id': data['donor_id'],
            'qurbani_order_line_ids': product_lines,
        })

        qurbani.calculate_amount()

        for line in qurbani.qurbani_order_line_ids:

            product_name = (line.product_id.name or "").lower()

            # ==================================================
            # COW
            # ==================================================
            if 'cow' in product_name:

                slaughter_records = self.env['qurbani.cow.slaughter'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('start_time', '=', line.slaughter_start_time),
                    ('end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                ], order='id asc')

                qurbani_cow_slaughter = False

                # PICK FIRST RECORD HAVING < 8 LINES
                for rec in slaughter_records:

                    current_count = len(rec.qurbani_cow_slaughter_line)

                    if current_count < 8:
                        qurbani_cow_slaughter = rec
                        break

                if not qurbani_cow_slaughter:
                    return {
                        "status": "error",
                        "body": "No empty cow slaughter slot available."
                    }

                # APPEND LINE
                qurbani_cow_slaughter.write({
                    'qurbani_cow_slaughter_line': [(0, 0, {
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                    })]
                })

                # UPDATE SLOT FULL
                qurbani_cow_slaughter.slot_full = len(
                    qurbani_cow_slaughter.qurbani_cow_slaughter_line
                )

                # DISTRIBUTION
                qurbani_cow_distribution = self.env['qurbani.cow.distribution'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('slaughter_start_time', '=', line.slaughter_start_time),
                    ('slaughter_end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                    ('start_time', '=', line.start_time),
                    ('end_time', '=', line.end_time),
                    ('distribution_location_id', '=', line.distribution_id.id),
                ], limit=1)

                if qurbani_cow_distribution:
                    qurbani_cow_distribution.write({
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                    })

            # ==================================================
            # GOAT
            # ==================================================
            elif 'goat' in product_name:

                slaughter_records = self.env['qurbani.goat.slaughter'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('start_time', '=', line.slaughter_start_time),
                    ('end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                ], order='id asc')

                qurbani_goat_slaughter = False

                # PICK FIRST RECORD HAVING < 8 LINES
                for rec in slaughter_records:

                    current_count = len(rec.qurbani_goat_slaughter_line)

                    if current_count < 8:
                        qurbani_goat_slaughter = rec
                        break

                if not qurbani_goat_slaughter:
                    return {
                        "status": "error",
                        "body": "No empty goat slaughter slot available."
                    }

                # APPEND LINE
                qurbani_goat_slaughter.write({
                    'qurbani_goat_slaughter_line': [(0, 0, {
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                    })]
                })

                # UPDATE SLOT FULL
                qurbani_goat_slaughter.slot_full = len(
                    qurbani_goat_slaughter.qurbani_goat_slaughter_line
                )

                # DISTRIBUTION
                qurbani_goat_distribution = self.env['qurbani.goat.distribution'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('slaughter_start_time', '=', line.slaughter_start_time),
                    ('slaughter_end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                    ('start_time', '=', line.start_time),
                    ('end_time', '=', line.end_time),
                    ('distribution_location_id', '=', line.distribution_id.id),
                ], limit=1)

                if qurbani_goat_distribution:
                    qurbani_goat_distribution.write({
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                    })
        
        # ==================================================
        # 8. SUCCESS
        # ==================================================
        return {
            "status": "success",
            "id": qurbani.id,
            "name": qurbani.name,
        }