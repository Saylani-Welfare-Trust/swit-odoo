from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_welfare = fields.Boolean('Is Welfare', tracking=True)
    is_hod = fields.Boolean('Is HOD', tracking=True, help="Added automatically to the disbursement lines when a welfare request reaches HOD Approval.")
