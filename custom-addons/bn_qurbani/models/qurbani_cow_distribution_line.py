from odoo import models, fields


class QurbaniCowDistributionLine(models.Model):
    _name = 'qurbani.cow.distribution.line'
    _description = "Qurbani Cow Distribution Line"


    qurbani_cow_distribution_id = fields.Many2one('qurbani.cow.distribution', string="Qurbani Cow Distribution")
    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')