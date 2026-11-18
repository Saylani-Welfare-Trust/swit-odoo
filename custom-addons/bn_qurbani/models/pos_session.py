from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_res_company(self):
        # OVERRIDE to load the fields in pos data (load_pos_data)
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['first_para_halfnama', 'second_para_halfnama', 'third_para_halfnama']

        return vals

    def _pos_data_process(self, loaded_data):
        super()._pos_data_process(loaded_data)

        params = self.env['ir.config_parameter'].sudo()
        loaded_data['enable_qurbani'] = bool(params.get_param('enable_qurbani', default=False))