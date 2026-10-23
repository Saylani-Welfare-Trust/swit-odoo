from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    
    is_medical_equipment = fields.Boolean(related='product_tmpl_id.is_medical_equipment', string="Is Medical Equipment", store=True, tracking=True)
    is_medical_equipment_donation = fields.Boolean(related='product_tmpl_id.is_medical_equipment_donation', string="Is Medical Equipment Donation", store=True, tracking=True)