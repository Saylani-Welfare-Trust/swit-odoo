from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    
    is_medical_equipment = fields.Boolean('Is Medical Equipment', tracking=True)
    is_medical_equipment_donation = fields.Boolean('Is Medical Equipment Donation', tracking=True)