from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_welfare = fields.Boolean('Is Welfare', tracking=True)