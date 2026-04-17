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
            if line.remarks:
                remarks.append(line.remarks)
        
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

        # -------------------------
        # 1. GROUP & CALCULATE FIRST
        # -------------------------
        for line in data['order_lines']:

            schedule = self.env['distribution.schedule'].search([
                ('pos_product_id', '=', line['product_id'])
            ], limit=1)

            if not schedule:
                continue

            qty = int(line['quantity'])

            if schedule.id not in schedule_usage:
                schedule_usage[schedule.id] = {
                    'schedule': schedule,
                    'qty': 0
                }

            schedule_usage[schedule.id]['qty'] += qty

        # -------------------------
        # 2. VALIDATION (IMPORTANT PART)
        # -------------------------
        for usage in schedule_usage.values():
            schedule = usage['schedule']
            new_qty = usage['qty']

            if (schedule.booked_hissa + new_qty) > schedule.total_hissa:
                return {
                    "status": "error",
                    "body": f"Not enough Hissa for {schedule.name}. "
                            f"Available: {schedule.total_hissa - schedule.booked_hissa}, "
                            f"Requested: {new_qty}",
                }

        # -------------------------
        # 3. APPLY UPDATES AFTER VALIDATION
        # -------------------------
        product_lines = []

        for line in data['order_lines']:

            schedule = self.env['distribution.schedule'].search([
                ('pos_product_id', '=', line['product_id'])
            ], limit=1)

            qty = int(line['quantity'])

            if schedule:
                schedule.booked_hissa += qty
                schedule.current_hissa += qty

            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
                'remarks': line.get('remarks', ''),
            }))

        # -------------------------
        # 4. CREATE ORDER
        # -------------------------
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