from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        vals = super()._loader_params_res_partner()
        vals["search_params"]["fields"] += ["categories"]
        return vals

    def _loader_params_res_users(self):
        vals = super()._loader_params_res_users()
        vals["search_params"]["fields"] += ["branch_code", "branch_name"]
        return vals
