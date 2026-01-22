from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    donation_box_product = fields.Char('Donation Box Product Name', tracking=True)
    
    donation_home_service_product = fields.Char('Donation Home Service Product Name', tracking=True)
    
    microfinance_intallement_product = fields.Char('Microfinance Installement Product Name', tracking=True)
    microfinance_security_depsoit_product = fields.Char('Microfinance Security Deposit Product Name', tracking=True)