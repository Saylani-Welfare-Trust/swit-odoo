from odoo import models, fields


class AdvanceDonationCategoryLine(models.Model):
    _name = 'advance.donation.category.line'
    _description = "Advance Donation Category Line"


    product_id = fields.Many2one('product.product', 'Product')
    category_id = fields.Many2one('advance.donation.category', 'Category')