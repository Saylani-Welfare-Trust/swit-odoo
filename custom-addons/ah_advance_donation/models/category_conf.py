from odoo import fields,api,models,_

class AdvDonCategory(models.Model):
    _name = 'adv.don.category'

    name = fields.Char('Name')
    category_lines = fields.One2many('adv.don.category.line', 'category_id')


class AdvDonCategoryLine(models.Model):
    _name = 'adv.don.category.line'

    product_id = fields.Many2one('product.product', 'Product')
    category_id = fields.Many2one('adv.don.category', 'Category ID')