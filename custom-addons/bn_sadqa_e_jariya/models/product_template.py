from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_sadqa_jariya = fields.Boolean('Is Sadqa e Jariya', tracking=True)
    is_sadqa_jariya_hod = fields.Boolean(
        'Is Sadqa e Jariya HOD', tracking=True,
        help="Added automatically to the disbursement lines when an application reaches HOD Approval.",
    )
