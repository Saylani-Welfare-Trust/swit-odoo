from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


class QurbaniOrder(models.Model):
    _name = 'qurbani.order'
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
        # raise ValidationError(str(data))

        schedule_usage = {}

        # ==================================================
        # 1. FIND EXACT DEMAND RECORD (ONLY SOURCE OF TRUTH)
        # ==================================================
        def _get_demand(line):
            slot = line.get('qurbani_schedule', {}).get('slot', {})

            return self.env['qurbani.demand'].search([
                ('pos_product_id', '=', line['product_id']),

                # slaughter window matching
                ('slaughter_location_id', '=', slot.get('slaughter').get('location', 0)),
                ('slaughter_start_time', '<=', slot.get('slaughter').get('start', 0)),
                ('slaughter_end_time', '>=', slot.get('slaughter').get('end', 0)),

                # distribution window matching
                ('distribution_location_id', '=', slot.get('distribution').get('location', 0)),
                ('distribution_start_time', '<=', slot.get('distribution').get('start', 0)),
                ('distribution_end_time', '>=', slot.get('distribution').get('end', 0)),

                # optional safety keys
                ('hijri_id', '=', self.env['hijri'].search([], order="id desc", limit=1).id),
            ], limit=1)

        # ==================================================
        # 2. GROUP & CALCULATE FIRST
        # ==================================================
        for line in data['order_lines']:
            demand = _get_demand(line)

            if not demand:
                continue

            qty = int(line['quantity'])

            if demand.id not in schedule_usage:
                schedule_usage[demand.id] = {
                    'demand': demand,
                    'qty': 0
                }

            schedule_usage[demand.id]['qty'] += qty

        # ==================================================
        # 3. VALIDATION
        # ==================================================
        for usage in schedule_usage.values():
            demand = usage['demand']
            new_qty = usage['qty']

            if (demand.booked_hissa + new_qty) > demand.total_hissa:
                return {
                    "status": "error",
                    "body": (
                        f"Not enough Hissa for {demand.id}. "
                        f"Available: {demand.total_hissa - demand.booked_hissa}, "
                        f"Requested: {new_qty}"
                    ),
                }

        # ==================================================
        # 4. APPLY UPDATES (NO CHANGE IN STRUCTURE)
        # ==================================================
        product_lines = []

        for line in data['order_lines']:

            demand = _get_demand(line)
            qty = int(line['quantity'])

            if demand:
                demand.booked_hissa += qty
                demand.current_hissa += qty

            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],

                'day_id': self.env['qurbani.day'].search([
                    ('name', '=', line['qurbani_schedule'].get('slot', {}).get('day', ''))
                ], limit=1).id,

                'city_id': self.env['stock.location'].search([
                    ('name', '=', line['qurbani_schedule'].get('city', ''))
                ], limit=1).id,

                'distribution_id': self.env['stock.location'].search([
                    ('name', '=', line['qurbani_schedule'].get('location', ''))
                ], limit=1).id,

                'hissa_name': line['qurbani_schedule'].get('name', ''),
                'start_time': line['qurbani_schedule'].get('slot', {}).get('start_time', 0),
                'end_time': line['qurbani_schedule'].get('slot', {}).get('end_time', 0),
            }))

        # ==================================================
        # 5. CREATE ORDER (UNCHANGED)
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