from odoo import models, fields


state_selection = [
    ('draft', 'Draft'),
    ('disbursed', 'Disbursed'),
]

collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]


class WelfareRecurringLine(models.Model):
    _name = 'welfare.recurring.line'
    _description = "Welfare Recurring Line"


    welfare_id = fields.Many2one('welfare', string="Welfare")
    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")

    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")

    marriage_date = fields.Date('Marriage Date', default=fields.Date.today())
    collection_date = fields.Date('Collection Date', default=fields.Date.today())

    amount = fields.Monetary('Amount', currency_field='currency_id')

    state = fields.Selection(selection=state_selection, string="Order Type")