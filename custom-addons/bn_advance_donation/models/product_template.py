from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_advance_donation = fields.Boolean('Is Advance Donation')
    is_service_charge = fields.Boolean(string="Is Service Charge")