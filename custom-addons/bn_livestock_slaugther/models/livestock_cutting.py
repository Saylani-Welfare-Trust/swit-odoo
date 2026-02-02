from odoo import models, fields


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received')
]


class LivestockCutting(models.Model):
    _name = 'livestock.cutting'
    _description = "Livestock Cutting"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')


    def action_confirm(self):
        pass
    
    def action_validate_picking(self):
        pass