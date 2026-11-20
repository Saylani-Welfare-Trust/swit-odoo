from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # only these products can be disbursement items of a Sadqa e Jariya application
    is_sadqa_jariya = fields.Boolean('Is Sadqa-e-Jaria', tracking=True)
    is_sadqa_jariya_hod = fields.Boolean(
        'Is Sadqa-e-Jaria HOD', tracking=True,
        help="Added automatically to the disbursement lines when an application reaches HOD Approval.",
    )
