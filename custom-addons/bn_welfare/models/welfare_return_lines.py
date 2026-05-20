from odoo import models, fields


class WelfareReturnLine(models.Model):
    _name = 'welfare.return.line'
    _description = 'Welfare Return Line'

    welfare_line_id = fields.Many2one('welfare.line')
    welfare_id = fields.Many2one('welfare')
    donee_id = fields.Many2one('res.partner')

    product_id = fields.Many2one('product.product')
    quantity = fields.Float()
    total_amount = fields.Float()

    return_date = fields.Date()
    state = fields.Selection([
        ('pending', 'Pending'),
        ('returned', 'Returned'),
    ], default='pending')