from odoo import models, fields, api
from odoo.exceptions import ValidationError


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


    @api.onchange('quantity')
    def _onchange_check_on_hand(self):
        if self.product_id and self.product_id.detailed_type != 'service':
            if self.quantity > self.product_id.free_qty:
                raise ValidationError('You have enter the quantity value greater then free quantity of the product.')