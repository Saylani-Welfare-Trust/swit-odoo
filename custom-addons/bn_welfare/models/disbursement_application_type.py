from odoo import models, fields


order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
    ('both', 'Both'),
]


class DisbursementApplicationType(models.Model):
    _name = 'disbursement.application.type'
    _description = "Disbursement Application Type"


    name = fields.Char('Name')

    order_type = fields.Selection(selection=order_type_selection, string="Order Type")

    product_category_id = fields.Many2one('product.category', string="Product Category")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    analytic_account_ids = fields.Many2many('account.analytic.account', string="Branch")
