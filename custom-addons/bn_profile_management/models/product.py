from odoo import fields, models, exceptions, _, api


class Product(models.Model):
    _inherit = 'product.product'


    is_course = fields.Boolean('Is Course', tracking=True)