from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        vals = super()._loader_params_res_partner()
        vals["search_params"]["fields"] += ["cnic_no"]
        return vals
