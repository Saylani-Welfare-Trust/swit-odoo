from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


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

    def set_remarks(self):
        remarks = []
        for line in self.qurbani_order_line_ids:
            remarks.append(f'{line.hissa_name} - {line.city_id.name} - {line.distribution_id.name} - {line.day_id.name}: {line.start_time} to {line.end_time}')
        
        self.remarks = "-".join(remarks)
    
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

            available = (demand.total_hissa or 0) - (demand.current_hissa or 0)

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

            schedule = line.get('qurbani_schedule', {})
            slot = schedule.get('slot', {})

            product_lines.append((0, 0, {
                'product_id': line.get('product_id'),
                'quantity': line.get('quantity'),
                'amount': line.get('price'),

                'day_id': self.env['qurbani.day'].search([
                    ('name', '=', slot.get('day'))
                ], limit=1).id,

                'city_id': self.env['stock.location'].search([
                    ('name', '=', schedule.get('city'))
                ], limit=1).id,

                'distribution_id': self.env['stock.location'].search([
                    ('name', '=', slot.get('distribution', {}).get('location'))
                ], limit=1).id,

                'hissa_name': schedule.get('name', ''),
                'start_time': slot.get('start_time', 0),
                'end_time': slot.get('end_time', 0),
            }))

        # ==================================================
        # 7. CREATE ORDER
        # ==================================================
        qurbani = self.env['qurbani.order'].create({
            'donor_id': data['donor_id'],
            'qurbani_order_line_ids': product_lines,
        })

        qurbani.calculate_amount()
        qurbani.set_remarks()

        return {
            "status": "success",
            "id": qurbani.id,
            "name": qurbani.name,
        }