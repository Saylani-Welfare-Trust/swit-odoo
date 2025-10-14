from odoo import models, fields, api
from odoo.exceptions import UserError


class swt_goat_dept(models.Model):
    _name = 'swt.goat_dept'
    _description = 'swt.goat_dept'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    product = fields.Many2one('product.template', string="Product", required=True)

    quantity = fields.Integer(
        string='Quantity',
    )

    price = fields.Float(
        string='Price',
    )

    product_code = fields.Char(
        string='Product Code',
        required=False)

    confirm_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    cutting_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)
    picking_id = fields.Many2one('stock.picking', string="Picking")

    state = fields.Selection([
        ('not_received', 'Not Received'),
        ('received', 'Received'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='not_received', string="Status")