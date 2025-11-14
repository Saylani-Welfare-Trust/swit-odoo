from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_microfinance = fields.Boolean('Is Microfinance', tracking=True)