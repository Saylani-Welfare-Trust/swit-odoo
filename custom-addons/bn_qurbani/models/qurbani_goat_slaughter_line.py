from odoo import models, fields


class QurbaniGoatSlaughterLine(models.Model):
    _name = 'qurbani.goat.slaughter.line'
    _description = "Qurbani Goat Slaughter Line"


    qurbani_goat_slaughter_id = fields.Many2one('qurbani.goat.slaughter', string="Qurbani Goat Slaughter")
    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')