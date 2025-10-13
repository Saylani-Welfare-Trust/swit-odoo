from odoo import api, fields, models




class ProductTemplate(models.Model):
    _inherit = 'product.product'



    is_epr  = fields.Boolean(
        string='Is EPR',
        required=False)
