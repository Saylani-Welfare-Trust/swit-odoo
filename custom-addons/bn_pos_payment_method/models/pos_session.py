from odoo import models


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_pos_payment_method(self):
        result = super(POSSession, self)._loader_params_pos_payment_method()
        result['search_params']['fields'].append('show_popup')
        result['search_params']['fields'].append('is_bank')
        result['search_params']['fields'].append('is_donation_in_kind')
        return result