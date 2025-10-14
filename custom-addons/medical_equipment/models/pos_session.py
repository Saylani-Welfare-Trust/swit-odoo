from odoo import api, fields, models,_
from odoo.exceptions import UserError



class PosSessionInherit(models.Model):
    _inherit = 'pos.session'

    def load_pos_data(self):
        loaded_data =super(PosSessionInherit, self).load_pos_data()
        return loaded_data
    
    def _loader_params_product_product(self):
        result = super(PosSessionInherit,self)._loader_params_product_product()
        result['search_params']['fields'].append('is_medical_equipment')
        
        return result

    def _loader_params_pos_category(self):
        domain = []
        if self.config_id.limit_categories and self.config_id.iface_available_categ_ids:
            domain = [('id', 'in', self.config_id.iface_available_categ_ids.ids)]
        print('-------------------------------------------------------------------------------')
        
        return {'search_params': {'domain': domain, 'fields': ['id', 'name', 'type', 'parent_id', 'child_id', 'write_date', 'has_image','is_medical_equipment']}}

