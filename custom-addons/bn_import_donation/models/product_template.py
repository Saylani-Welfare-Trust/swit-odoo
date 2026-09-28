from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_course = fields.Boolean('Is Course', tracking=True)