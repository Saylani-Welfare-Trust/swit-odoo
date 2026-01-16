from odoo import models, fields, api


collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]

order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
    ('both', 'Both'),
]

recurring_duration_selection = [
    ('3_M', '3 Months'),
    ('4_M', '4 Months'),
    ('5_M', '5 Months'),
    ('6_M', '6 Months'),
    ('7_M', '7 Months'),
    ('8_M', '8 Months'),
    ('9_M', '9 Months'),
    ('10_M', '10 Months'),
    ('11_M', '11 Months'),
    ('12_M', '12 Months'),
]


class WelfareLine(models.Model):
    _name = 'welfare.line'
    _description = "Welfare Line"


    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)

    order_type = fields.Selection(selection=order_type_selection, string="Order Type")
    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")
    recurring_duration = fields.Selection(selection=recurring_duration_selection, string="Recurring Duration")

    welfare_id = fields.Many2one('welfare', string="Welfare")
    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )


    marriage_date = fields.Date('Marriage Date', default=fields.Date.today())
    collection_date = fields.Date('Collection Date', default=fields.Date.today())
    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Float(
        'Amount',
        related='product_id.list_price',
        store=True,
    )

    total_amount = fields.Float(
        'Total Amount',
        compute='_compute_total_amount',
        store=True
    )

    @api.depends('quantity', 'amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = rec.quantity * rec.amount
            
    @api.depends('disbursement_application_type_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = ""

            category_id = rec.disbursement_application_type_id.product_category_id.id
            
            if category_id:
                rec.product_domain = str([('categ_id', '=', category_id), ('is_welfare', '=', True)])