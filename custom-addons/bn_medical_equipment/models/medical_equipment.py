from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


status_selection = [       
    ('draft', 'Draft'),
    ('payment_received', 'Payment Received'),
    ('validate', 'Validate'),
    ('payment_return','Payment Return'),
    ('return', 'Return')
]


class MedicalEquipment(models.Model):
    _name = 'medical.equipment'
    _description = "Medical Equipment"


    donee_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Stock Picking")

    name = fields.Char('Name')
    mobile = fields.Char(related='donee_id.mobile', string="Mobile No.")

    state = fields.Selection(selection=status_selection, string="Status", default="draft")

    amount = fields.Monetary('Amount', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    medical_equipment_line_ids = fields.One2many('medical.equipment.line', 'medical_equipment_id', string="Medical Equipments")


    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('medical_equipment') or ('New')

        return super(MedicalEquipment, self).create(vals)
    
    def calculate_amount(self):
        self.amount = sum(line.amount for line in self.medical_equipment_line_ids)

    def action_validate(self):
        raise ValidationError('Functionality Coming soon')
    
    def action_return(self):
        raise ValidationError('Functionality Coming soon')
    
    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Opertaion',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }

    @api.model
    def create_me_record(self, data):
        product_lines = []

        for line in data['order_lines']:
            # Assuming 'product_id' is a valid product ID
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
            }))
        
        me = self.env['medical.equipment'].create({
            'donee_id': data['donee_id'],
            'medical_equipment_line_ids': product_lines
        })

        for line in me.medical_equipment_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price

            for tax in taxes:
                if tax.amount_type == 'percent':
                    tax_amount = base_price * (tax.amount / 100)

                    total_price_incl_tax += tax_amount
                else:
                    total_price_incl_tax += tax.amount

            line.amount = total_price_incl_tax * line.quantity

        me.calculate_amount()
       
        return{
            "status": "success",
            "id": me.id
        }
    
    @api.model
    def get_me_record(self, data):
        """Fetch ME record by name and return product information"""
        # Search for the ME record
        me = self.sudo().search([('name', '=', data['name']), ('state', '!=', 'paid')], limit=1)
        
        if not me:
            return {
                "status": "error",
                "body": f"Donation Home Service record with reference {data['name']} not found."
            }
        
        if me.state not in ['gate_pass', 'gate_in']:
            return {
                "status": "error",
                "body": f"Current status of {data['name']} is in a {me.state.capitalize()}."
            }
        
        # Prepare product data for POS
        products_data = []
        
        # Add regular product lines
        for line in me.medical_equipment_line_ids:
            product = line.product_id
            products_data.append({
                'product_id': product.id,
                'name': product.name,
                'quantity': line.quantity,
                'price': product.lst_price,
                'default_code': product.default_code,
                'category': product.categ_id.name if product.categ_id else ''
            })
        
        return {
            'id': me.id,
            'name': me.name,
            'donee_id': me.donee_id.id if me.donee_id else False,
            'donor_name': me.donee_id.name if me.donee_id else '',
            'products': products_data,
            'success': True
        }