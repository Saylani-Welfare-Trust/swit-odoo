from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    
    microfinance_intallement_product = fields.Char('Microfinance Installement', tracking=True)
    microfinance_security_depsoit_product = fields.Char('Microfinance Security Deposit', tracking=True)
    
    medical_equipment_security_depsoit_product = fields.Char('Medical Equipment Security Deposit', tracking=True)