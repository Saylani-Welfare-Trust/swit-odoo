from odoo import models, fields


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received')
]


class LivestockSlaughter(models.Model):
    _name = 'livestock.slaugther'
    _description = "Livestock Slaugther"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donee_id = fields.Many2one('res.partner', string="Donee")
    product_id = fields.Many2one('product.product', string="Product")
    location_id = fields.Many2one('stock.location', string="Location")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)
    ref = fields.Char('Source Document')

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')


    def action_confirm(self):
        pass

    def action_cutting(self):
        pass
    
    def action_open_wizard(self):
        pass