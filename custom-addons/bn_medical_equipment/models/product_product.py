from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    
    is_medical_equipment = fields.Boolean(related='product_tmpl_id.is_medical_equipment', string="Is Medical Equipment", store=True, tracking=True)
    is_medical_approval = fields.Boolean(related='product_tmpl_id.is_medical_approval', string="Is Medical Approval", store=True, tracking=True)


    security_deposit = fields.Monetary(related='product_tmpl_id.security_deposit', string="Security Deposit", store=True, tracking=True)

    recovery_period = fields.Integer(related='product_tmpl_id.recovery_period', string="Recovery Period", store=True, tracking=True)