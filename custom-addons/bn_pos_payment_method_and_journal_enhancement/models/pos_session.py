from odoo import models, fields


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].append('popup')
        return result