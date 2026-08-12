from odoo import models


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        
        result['search_params']['fields'].append('is_donation_in_kind')

        return result