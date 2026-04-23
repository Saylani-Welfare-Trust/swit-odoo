from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_res_company(self):
        # OVERRIDE to load the fields in pos data (load_pos_data)
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['halfnama']
        
        return vals