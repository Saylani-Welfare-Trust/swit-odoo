from odoo import models, fields

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    product_tmpl_id = fields.Many2one('product.template', domain=[('is_kitchen', '=', True)], string="Product Template")
    product_id = fields.Many2one('product.product', domain=[('is_kitchen', '=', True)], string="Product")  