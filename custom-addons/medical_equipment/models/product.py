from odoo import models, fields,api
from odoo.exceptions import UserError





class ProductProduct(models.Model):
    _inherit = 'product.product'

    
    is_medical_equipment= fields.Boolean(string="Medical Equipment",default=False)
    


class PosCategory(models.Model):
    _inherit = 'pos.category'

    is_medical_equipment = fields.Boolean(string="Medical Equipment",default=False)