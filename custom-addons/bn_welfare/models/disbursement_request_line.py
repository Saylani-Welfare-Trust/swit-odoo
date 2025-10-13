from odoo import fields, models, api


collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]

order_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'), 
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


class DisbursementRequestLine(models.Model):
    _name = 'disbursement.request.line'
    _description = "Disbursement Request Line"


    disbursement_request_id = fields.Many2one('disbursement.request', string="Disbursement Request ID")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Catgeory ID")
    branch_id = fields.Many2one('res.company', string="Branch ID", default=lambda self: self.env.company.id)
    disbursement_type_id = fields.Many2one('disbursement.type', string="Disbursement Type ID")
    product_id = fields.Many2one('product.product', string="Product ID")
    warehouse_loc_id = fields.Many2one('stock.location', string="Warehouse/Location ID")

    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)


    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    disbursement_amount = fields.Monetary('Amount', currency_field='currency_id')

    collection_date = fields.Date('Collection Date', default=fields.Date.today())
    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point")
    marriage_date = fields.Date('Marriage Date', default=fields.Date.today())

    order_type = fields.Selection(selection=order_selection, string="Order Type")
    recurring_duration = fields.Selection(selection=recurring_duration_selection, string="Recurring Duration")
    disbursement_category_name = fields.Char(related='disbursement_category_id.name', string="Disbursement Catgeory Name")


    @api.depends('disbursement_type_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = ""

            category_id = rec.disbursement_type_id.product_category_id.id
            
            if category_id:
                rec.product_domain = str([('categ_id', '=', category_id)])