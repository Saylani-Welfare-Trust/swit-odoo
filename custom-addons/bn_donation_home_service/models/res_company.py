from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    
    donation_home_service_product = fields.Char('Donation Home Service', tracking=True)