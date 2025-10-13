from odoo import api, fields, models, _

class POSSessionModelInherit(models.Model):
    _inherit = 'product.template'

    check_stock = fields.Boolean(string='Live Stock')

