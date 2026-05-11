from odoo import models, fields


class QurbaniCowSlaughterLine(models.Model):
    _name = 'qurbani.cow.slaughter.line'
    _description = "Qurbani Cow Slaughter Line"


    qurbani_cow_slaughter_id = fields.Many2one('qurbani.cow.slaughter', string="Qurbani Cow Slaughter")
    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')