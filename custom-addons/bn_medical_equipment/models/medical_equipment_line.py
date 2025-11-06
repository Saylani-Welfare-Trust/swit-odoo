from odoo import models, fields


class DonationHomeServiceLine(models.Model):
    _name = 'medical.equipment.line'
    _description = "Medical Equipment Line"


    medical_equipment_id = fields.Many2one('medical.equipment', string="Donation Home Service")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', related='medical_equipment_id.currency_id')
    
    quantity = fields.Integer('Quantity', default=1)
    amounts = fields.Float(
    string='Amount', 
    related='product_id.lst_price',
    readonly=True
)

    