from odoo import models, fields, api
from odoo.exceptions import UserError


class SWT_kitchen_transfer(models.Model):
    _name = 'swt.kitchen_transfer'
    _description = 'swt.kitchen.transfer'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    product = fields.Many2one('product.product', string="Product", required=True)

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