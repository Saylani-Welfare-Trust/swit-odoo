from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_company(self):
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['microfinance_intallement_product', 'microfinance_security_depsoit_product']
        return vals
