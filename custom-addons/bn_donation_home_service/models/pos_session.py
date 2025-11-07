from odoo import models, fields


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('is_livestock')
        result['search_params']['fields'].append('detailed_type')
        return result