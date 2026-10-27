from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    
    donation_home_service_product = fields.Char('Donation Home Service', tracking=True)
    
    medical_equipment_security_depsoit_product = fields.Char('Medical Equipment Security Deposit', tracking=True)
    welfare_product = fields.Char('Welfare Product', tracking=True)