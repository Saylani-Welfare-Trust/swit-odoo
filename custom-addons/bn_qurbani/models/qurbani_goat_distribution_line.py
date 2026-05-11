from odoo import models, fields


class QurbaniGoatDistributionLine(models.Model):
    _name = 'qurbani.goat.distribution.line'
    _description = "Qurbani Goat Distribution Line"


    qurbani_goat_distribution_id = fields.Many2one('qurbani.goat.distribution', string="Qurbani Goat Distribution")
    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')