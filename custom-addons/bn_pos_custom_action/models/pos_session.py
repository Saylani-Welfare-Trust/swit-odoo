from odoo import models, fields


class PosSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_res_company(self):
        # OVERRIDE to load the fields in pos data (load_pos_data)
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['donation_box_product', 'donation_home_service_product', 'microfinance_intallement_product', 'microfinance_security_depsoit_product', 'medical_equipment_security_depsoit_product']
        
        return vals