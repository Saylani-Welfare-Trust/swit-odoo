from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    
    is_medical_equipment = fields.Boolean('Is Medical Equipment', tracking=True)
    is_medical_approval = fields.Boolean('Is Medical Approval', tracking=True)

    security_deposit = fields.Monetary('Security Deposit')

    recovery_period = fields.Integer('Recovery Period')