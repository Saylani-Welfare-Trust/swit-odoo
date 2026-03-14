from odoo import models, fields


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received'),
    ('in_progress', 'In Progress'),
    ('done', 'Done'),
]


class MeatDepartment(models.Model):
    _name = 'meat.department'
    _description = 'Meat Department'


    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    product_id = fields.Many2one('product.product', string="Product")
    picking_id = fields.Many2one('stock.picking', string="Picking")

    quantity = fields.Integer('Quantity')

    price = fields.Float('Price')

    product_code = fields.Char('Product Code')

    confirm_hide = fields.Boolean('Confirm Hide')

    cutting_hide = fields.Boolean('Cutting Hide')

    state = fields.Selection(selection=state_selection, default='not_received', string="Status")