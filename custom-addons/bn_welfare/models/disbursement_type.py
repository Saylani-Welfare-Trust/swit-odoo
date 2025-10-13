from odoo import fields, models, api, exceptions


order_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
    ('both', 'Both'), 
]


class DisbursementType(models.Model):
    _name = 'disbursement.type'
    _description = 'Disbursement Type'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)

    # product_id = fields.Many2one('product.product', string="Product ID", tracking=True)
    product_category_id = fields.Many2one('product.category', string="Product Category ID", tracking=True)
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category ID", tracking=True)

    order_type = fields.Selection(selection=order_selection, string="Order Type", tracking=True)