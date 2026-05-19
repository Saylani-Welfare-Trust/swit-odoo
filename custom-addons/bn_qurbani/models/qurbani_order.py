from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re
import json
from datetime import datetime, time
_logger = logging.getLogger(__name__)
from datetime import datetime


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

    is_sync = fields.Boolean('Is Sync')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_order') or ('New')

        return super(QurbaniOrder, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.qurbani_order_line_ids)
    
    def create_web_qurbani_order(self, donation_record, donation_name=None):
        """
        Create Qurbani Order from api.donation using slaughter‑slot logic.
        donation_name: optional, for better logging
        """
        # ---------- Helper: get day from name ----------
        def _get_day_from_name(day_name):
            if not day_name:
                return self.env['qurbani.day']
            return self.env['qurbani.day'].search([('name', '=', day_name)], limit=1)

        # ---------- Helper: get latest hijri (same as POS method) ----------
        def _get_latest_hijri():
            return self.env['hijri'].search([], order='id desc', limit=1)

        def convert_to_24hr(time_str):
            if not time_str:
                return False
            try:
                return datetime.strptime(time_str.strip(), "%I:%M %p").strftime("%H:%M:%S")
            except:
                return time_str

        # ---------- Helper: get demand for a donation line ----------
        def _get_demand(line, default_day, default_hijri, default_product):
            product = line.product_id or default_product
            if not product:
                raise ValidationError(f"Line {line.id if line else '?'} has no product_id")

            # Get slaughter center (web model)
            slaughter_center = self.env['web.qurbani.slaughter.center'].search([], limit=1, order='id desc')
            if not slaughter_center:
                raise ValidationError("No web.qurbani.slaughter.center found")
            slaughter_location_id = slaughter_center.slaughter_center_id.id

            day_id = line.day_id.id if line.day_id else (default_day.id if default_day else False)
            hijri_id = line.hijri_id.id if line.hijri_id else (default_hijri.id if default_hijri else False)

            if not day_id or not hijri_id:
                raise ValidationError(f"Cannot determine day/hijri for line {line.id}. day={day_id}, hijri={hijri_id}")

            demand_domain = [
                ('day_id', '=', day_id),
                ('hijri_id', '=', hijri_id),
                ('slaughter_location_id', '=', slaughter_location_id),
                ('remaining_hissa', '>', 0),
            ]
            # You can uncomment the product filter later if needed:
            # demand_domain.append(('inventory_product_id', '=', product.id))

            demand = self.env['qurbani.slaughter.slot.demand'].search(demand_domain, limit=1)
            if not demand:
                raise ValidationError(f"No available demand slot for day {day_id}, hijri {hijri_id}, product {product.name}")
            return demand

        # ---------- Main logic ----------
        try:
            donation_lines = donation_record.get('qurbani_order_line_ids', [])
            if isinstance(donation_lines, list) and donation_lines and isinstance(donation_lines[0], int):
                donation_lines = self.env['api.qurbani.order.line'].browse(donation_lines).exists()
            elif not donation_lines:
                donation_lines = []

            default_day = _get_day_from_name(donation_record.get('qurbani_day'))
            default_hijri = _get_latest_hijri()
            default_product = False

            schedule_usage = {}
            order_lines_data = []
            line_errors = []

            for api_line in donation_lines:
                if not api_line.exists():
                    line_errors.append(f"Line ID {api_line.id} does not exist")
                    continue

                try:
                    demand = _get_demand(api_line, default_day, default_hijri, default_product)
                except ValidationError as e:
                    error_msg = str(e)
                    line_errors.append(f"Line {api_line.id} (product: {api_line.product_id.name if api_line.product_id else '?'}) - {error_msg}")
                    _logger.warning(f"Line {api_line.id} error: {error_msg}")
                    continue

                qty = int(api_line.quantity or 1)

                if demand.id not in schedule_usage:
                    schedule_usage[demand.id] = {'demand': demand, 'qty': 0}
                schedule_usage[demand.id]['qty'] += qty

                order_lines_data.append({
                    'api_line': api_line,
                    'demand': demand,
                    'quantity': qty,
                    'product_id': api_line.product_id.id,
                    'amount': api_line.amount or 0.0,
                    'hissa_name': api_line.hissa_name or '',
                    'branch': api_line.branch or '',
                    'city_id': api_line.city_id.id if api_line.city_id else False,
                    'distribution_id': api_line.distribution_id.id if api_line.distribution_id else False,
                })

            if not order_lines_data:
                error_summary = "; ".join(line_errors) if line_errors else "No donation lines found or all lines invalid"
                donor_name = donation_name or donation_record.get('name', 'Unknown')
                donation_id = donation_record.get('id', 'Unknown')
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    donation_json = json.dumps(donation_record, indent=2, default=str)
                except:
                    donation_json = str(donation_record)
                detailed_reason = f"""
                    ================== NO VALID ORDER LINES ==================
                    Timestamp: {timestamp}
                    Donation Name: {donor_name}
                    Donation ID: {donation_id}
                    Error Summary: {error_summary}
                    COMPLETE DONATION RECORD: {donation_json}
                    ========================================================"""
                self.env['fetch.qurbani.log'].create({
                    'name': f"✗ NO VALID LINES [{timestamp}] - [ID-{donation_id}] {donor_name}",
                    'status': 'Error',
                    'reason': detailed_reason
                })
                return {"status": "error", "message": f"No valid qurbani lines found: {error_summary}"}

            # Validate and update demand slots
            for usage in schedule_usage.values():
                demand = usage['demand']
                requested = usage['qty']
                available = demand.remaining_hissa
                if requested > available:
                    donor_name = donation_name or donation_record.get('name', 'Unknown')
                    donation_id = donation_record.get('id', 'Unknown')
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        donation_json = json.dumps(donation_record, indent=2, default=str)
                    except:
                        donation_json = str(donation_record)
                    detailed_reason = f"""
                        ================== NOT ENOUGH HISSA ==================
                        Timestamp: {timestamp}
                        Donation Name: {donor_name}
                        Donation ID: {donation_id}
                        Demand ID: {demand.id}
                        Need {requested} hissa, only {available} available
                        COMPLETE DONATION RECORD: {donation_json}
                        ===================================================="""
                    self.env['fetch.qurbani.log'].create({
                        'name': f"✗ NOT ENOUGH HISSA [{timestamp}] - [ID-{donation_id}] {donor_name}",
                        'status': 'Error',
                        'reason': detailed_reason
                    })
                    return {"status": "error", "message": f"Not enough hissa for demand {demand.id}. Available: {available}, Requested: {requested}"}

            for usage in schedule_usage.values():
                demand = usage['demand']
                incoming_hissa = usage['qty']
                product_name = (demand.inventory_product_id.name or '').lower()
                divisor = 7 if 'cow' in product_name else 1
                total_hissa = (demand.current_hissa or 0) + incoming_hissa
                completed_animals = int(total_hissa // divisor)
                remaining_hissa = total_hissa % divisor
                new_remaining_demand = max((demand.remaining_demand or 0) - completed_animals, 0)
                demand.write({
                    'current_hissa': remaining_hissa,
                    'booked_hissa': (demand.booked_hissa or 0) + incoming_hissa,
                    'remaining_demand': new_remaining_demand,
                })

            # Build order lines
            product_lines = []
            for line_data in order_lines_data:
                demand = line_data['demand']
                api_line = line_data['api_line']
                city_id = api_line.city_id.id if api_line.city_id else False
                if not city_id and demand.slaughter_location_id.location_id:
                    city_id = demand.slaughter_location_id.location_id.id

                vals = {
                    'product_id': line_data['product_id'],
                    'quantity': line_data['quantity'],
                    'amount': line_data['amount'],
                    'day_id': demand.day_id.id,
                    'hijri_id': demand.hijri_id.id,
                    'city_id': city_id,
                    'distribution_id': line_data['distribution_id'],  # may be False
                    'slaughter_id': demand.slaughter_location_id.id,
                    'hissa_name': line_data['hissa_name'],
                    'start_time': demand.start_time,
                    'end_time': demand.end_time,
                    'slaughter_start_time': convert_to_24hr(demand.start_time),
                    'slaughter_end_time': convert_to_24hr(demand.end_time),
                }
                product_lines.append((0, 0, vals))

            # Donor and currency
            donor_id = donation_record.get('donor_id')
            if isinstance(donor_id, tuple):
                donor_id = donor_id[0]
            if donor_id and isinstance(donor_id, int):
                donor = self.env['res.partner'].browse(donor_id).exists()
                if not donor:
                    donor_id = False

            currency_name = donation_record.get('currency', 'USD')
            currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
            if not currency:
                currency = self.env.company.currency_id

            qurbani_order = self.create({
                'donor_id': donor_id or False,
                'currency_id': currency.id,
                'remarks': donation_record.get('remarks', ''),
                'amount': float(donation_record.get('total_amount', 0.0)),
                'qurbani_order_line_ids': product_lines,
                'pos_qurbani_order': False,
                'api_response_id': donation_record.get('import_id', ''),
                'donation_type': donation_record.get('donation_type', ''),
                'donation_from': donation_record.get('donation_from', ''),
                'dn_number': donation_record.get('dn_number', ''),
                'bank_charges': float(donation_record.get('bank_charges', 0.0)),
                'transaction_id': donation_record.get('transaction_id', ''),
                'api_currency': donation_record.get('currency', ''),
                'api_created_at': donation_record.get('created_at'),
                'api_updated_at': donation_record.get('updated_at'),
                'donor_phone': donation_record.get('phone', ''),
                'donor_email': donation_record.get('email', ''),
                'donor_cnic': donation_record.get('cnic', ''),
                'donor_country': donation_record.get('country', ''),
                'donor_ip_address': donation_record.get('ip_address', ''),
                'subscription_news': bool(donation_record.get('subscription_for_news', False)),
                'subscription_whatsapp': bool(donation_record.get('subscription_for_whatsapp', False)),
                'subscription_sms': bool(donation_record.get('subscription_for_sms', False)),
            })

            # -----------------------------------------------------------------
            # Link Slaughter and Distribution for each line
            # -----------------------------------------------------------------
            for line in qurbani_order.qurbani_order_line_ids:
                product_name = (line.product_id.name or "").lower()

                # ---------- SLAUGHTER LINKING (always) ----------
                if 'cow' in product_name:
                    slaughter_records = self.env['qurbani.cow.slaughter'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('start_time', '=', line.slaughter_start_time),
                        ('end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                    ], order='id asc')
                    qurbani_cow_slaughter = False
                    for rec in slaughter_records:
                        if len(rec.qurbani_cow_slaughter_line) < 7:
                            qurbani_cow_slaughter = rec
                            break
                    if qurbani_cow_slaughter:
                        qurbani_cow_slaughter.write({
                            'qurbani_cow_slaughter_line': [(0, 0, {
                                'qurbani_order_no': line.qurbani_order_id.name,
                                'qurbani_order_line_no': line.name,
                                'hissa_name': line.hissa_name,
                                'product_id': line.product_id.id,
                            })]
                        })
                        qurbani_cow_slaughter.slot_full = len(qurbani_cow_slaughter.qurbani_cow_slaughter_line)
                        self.env['fetch.qurbani.log'].create({
                            'name': f"✓ COW SLAUGHTER LINKED - Order {line.qurbani_order_id.name}, Line {line.name}",
                            'status': 'Success',
                            'reason': f"Slaughter slot ID {qurbani_cow_slaughter.id} (now has {qurbani_cow_slaughter.slot_full}/7 lines)"
                        })
                    else:
                        # Detailed logging for failure
                        available_slots = self.env['qurbani.cow.slaughter'].search([
                            ('day_id', '=', line.day_id.id),
                            ('hijri_id', '=', line.hijri_id.id),
                            ('slaughter_location_id', '=', line.slaughter_id.id),
                        ])
                        slot_info = []
                        for s in available_slots:
                            slot_info.append(f"ID {s.id}: {len(s.qurbani_cow_slaughter_line)}/7 lines, times {s.start_time}-{s.end_time}")
                        self.env['fetch.qurbani.log'].create({
                            'name': f"⚠ COW SLAUGHTER NOT FOUND - Order {line.qurbani_order_id.name}, Line {line.name}",
                            'status': 'Warning',
                            'reason': f"No available cow slaughter slot matching criteria. "
                                    f"day={line.day_id.id}, hijri={line.hijri_id.id}, location={line.slaughter_id.id}, "
                                    f"slaughter_start={line.slaughter_start_time}, slaughter_end={line.slaughter_end_time}. "
                                    f"Existing slots: {', '.join(slot_info) if slot_info else 'None'}"
                        })
                elif 'goat' in product_name:
                    qurbani_goat_slaughter = self.env['qurbani.goat.slaughter'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('start_time', '=', line.slaughter_start_time),
                        ('end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('qurbani_order_no', '=', False),
                    ], limit=1)
                    if qurbani_goat_slaughter:
                        qurbani_goat_slaughter.write({
                            'qurbani_order_no': line.qurbani_order_id.name,
                            'qurbani_order_line_no': line.name,
                            'hissa_name': line.hissa_name,
                            'product_id': line.product_id.id,
                        })
                        self.env['fetch.qurbani.log'].create({
                            'name': f"✓ GOAT SLAUGHTER LINKED - Order {line.qurbani_order_id.name}, Line {line.name}",
                            'status': 'Success',
                            'reason': f"Slaughter slot ID {qurbani_goat_slaughter.id}"
                        })
                    else:
                        self.env['fetch.qurbani.log'].create({
                            'name': f"⚠ GOAT SLAUGHTER NOT FOUND - Order {line.qurbani_order_id.name}, Line {line.name}",
                            'status': 'Warning',
                            'reason': f"No available goat slaughter slot for day {line.day_id.id}, hijri {line.hijri_id.id}, location {line.slaughter_id.id}"
                        })

                # ---------- DISTRIBUTION LINKING (only if distribution_id exists) ----------
                if line.distribution_id:
                    self.env['fetch.qurbani.log'].create({
                        'name': f"Distribution ID present - Order {line.qurbani_order_id.name}, Line {line.name}",
                        'status': 'Info',
                        'reason': f"Distribution ID: {line.distribution_id.id}"
                    })

                    # --- Search for an UNUSED distribution record ---
                    search_domain = [
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('qurbani_order_no', '=', False),   # CRITICAL: only unused records
                        # Uncomment these fields for stricter matching (recommended):
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        # ('distribution_location_id', '=', line.distribution_id.id),
                    ]
                    if 'cow' in product_name:
                        qurbani_cow_distribution = self.env['qurbani.cow.distribution'].search(search_domain, limit=1)
                        if qurbani_cow_distribution:
                            qurbani_cow_distribution.write({
                                'qurbani_order_no': line.qurbani_order_id.name,
                                'qurbani_order_line_no': line.name,
                                'hissa_name': line.hissa_name,
                                'product_id': line.product_id.id,
                                'start_time': line.start_time,
                                'end_time': line.end_time,
                                'distribution_location_id': line.distribution_id.id,
                                'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                            })
                            self.env['fetch.qurbani.log'].create({
                                'name': f"✓ COW DISTRIBUTION LINKED - Order {line.qurbani_order_id.name}, Line {line.name}",
                                'status': 'Success',
                                'reason': f"Distribution record ID {qurbani_cow_distribution.id} (was unused)"
                            })
                        else:
                            # Log failure with details
                            all_unused = self.env['qurbani.cow.distribution'].search([
                                ('slaughter_location_id', '=', line.slaughter_id.id),
                                ('qurbani_order_no', '=', False)
                            ])
                            self.env['fetch.qurbani.log'].create({
                                'name': f"✗ COW DISTRIBUTION NOT FOUND - Order {line.qurbani_order_id.name}, Line {line.name}",
                                'status': 'Error',
                                'reason': f"No unused cow distribution matching domain {search_domain}. "
                                        f"Total unused distributions for this slaughter location: {len(all_unused)}. "
                                        f"Distribution ID from API line: {line.distribution_id.id}. "
                                        f"Consider creating more distribution records."
                            })
                    elif 'goat' in product_name:
                        # Similar fix for goat distribution
                        qurbani_goat_distribution = self.env['qurbani.goat.distribution'].search(search_domain, limit=1)
                        if qurbani_goat_distribution:
                            qurbani_goat_distribution.write({
                                'qurbani_order_no': line.qurbani_order_id.name,
                                'qurbani_order_line_no': line.name,
                                'hissa_name': line.hissa_name,
                                'product_id': line.product_id.id,
                                'start_time': line.start_time,
                                'end_time': line.end_time,
                                'distribution_location_id': line.distribution_id.id,
                                'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                            })
                            self.env['fetch.qurbani.log'].create({
                                'name': f"✓ GOAT DISTRIBUTION LINKED - Order {line.qurbani_order_id.name}, Line {line.name}",
                                'status': 'Success',
                                'reason': f"Distribution record ID {qurbani_goat_distribution.id}"
                            })
                        else:
                            self.env['fetch.qurbani.log'].create({
                                'name': f"✗ GOAT DISTRIBUTION NOT FOUND - Order {line.qurbani_order_id.name}, Line {line.name}",
                                'status': 'Error',
                                'reason': f"No unused goat distribution matching domain {search_domain}"
                            })
                else:
                    self.env['fetch.qurbani.log'].create({
                        'name': f"Distribution SKIPPED - Order {line.qurbani_order_id.name}, Line {line.name}",
                        'status': 'Info',
                        'reason': "No distribution_id on this line. Only slaughter linking performed."
                    })


            return {
                "status": "success",
                "qurbani_order_id": qurbani_order.id,
                "name": qurbani_order.name,
                "message": "Web Qurbani Order created with slaughter integration"
            }

        except Exception as e:
            try:
                donation_json = json.dumps(donation_record, indent=2, default=str)
            except:
                donation_json = str(donation_record)
            donor_name = donation_name or donation_record.get('name', 'Unknown')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            donation_id = donation_record.get('id', 'Unknown')
            error_log_message = f"✗ FAILED [{timestamp}] - [ID-{donation_id}] {donor_name}"
            error_log_reason = f"""
                ================== DONATION PROCESSING FAILED ==================
                Timestamp: {timestamp}
                Donation Name: {donor_name}
                Donation ID: {donation_id}
                ERROR MESSAGE: {str(e)}
                COMPLETE DONATION RECORD OBJECT: {donation_json}
                ================================================================"""
            self.env['fetch.qurbani.log'].create({
                'name': error_log_message,
                'status': 'Error',
                'reason': error_log_reason
            })
            _logger.error(f"Error creating web qurbani order for {donor_name} (ID: {donation_id}): {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
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
            'is_sync': True
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
                    ('state', '!=', 'transfer'),
                ], order='id asc')

                qurbani_cow_slaughter = False

                # PICK FIRST RECORD HAVING < 8 LINES
                for rec in slaughter_records:

                    current_count = len(rec.qurbani_cow_slaughter_line)

                    if current_count < 7:
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
                    ('qurbani_order_no', '=', False),
                ], limit=1)

                if qurbani_cow_distribution:
                    qurbani_cow_distribution.write({
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                        'start_time': line.start_time,
                        'end_time': line.end_time,
                        'distribution_location_id': line.distribution_id.id,
                        'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                    })

            # ==================================================
            # GOAT
            # ==================================================
            elif 'goat' in product_name:

                qurbani_goat_slaughter = self.env['qurbani.goat.slaughter'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('start_time', '=', line.slaughter_start_time),
                    ('end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                    ('qurbani_order_no', '=', False),
                    ('state', '!=', 'transfer'),
                ], limit=1)

                if qurbani_goat_slaughter:
                    qurbani_goat_slaughter.write({
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                    })

                # DISTRIBUTION
                qurbani_goat_distribution = self.env['qurbani.goat.distribution'].search([
                    ('day_id', '=', line.day_id.id),
                    ('hijri_id', '=', line.hijri_id.id),
                    ('slaughter_start_time', '=', line.slaughter_start_time),
                    ('slaughter_end_time', '=', line.slaughter_end_time),
                    ('slaughter_location_id', '=', line.slaughter_id.id),
                    ('qurbani_order_no', '=', False),
                ], limit=1)

                if qurbani_goat_distribution:
                    qurbani_goat_distribution.write({
                        'qurbani_order_no': line.qurbani_order_id.name,
                        'qurbani_order_line_no': line.name,
                        'hissa_name': line.hissa_name,
                        'product_id': line.product_id.id,
                        'start_time': line.start_time,
                        'end_time': line.end_time,
                        'distribution_location_id': line.distribution_id.id,
                        'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                    })
        
        qurbani.is_sync = True

        # ==================================================
        # 8. SUCCESS
        # ==================================================
        return {
            "status": "success",
            "id": qurbani.id,
            "name": qurbani.name,
        }