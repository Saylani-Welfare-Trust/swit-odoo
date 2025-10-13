from odoo import api, fields, models, _

class POSSessionModelInherit(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_category(self):
        domain = []
        if self.config_id.limit_categories and self.config_id.iface_available_categ_ids:
            domain = [('id', 'in', self.config_id.iface_available_categ_ids.ids)]
        return {'search_params': {'domain': domain, 'fields': ['id', 'name', 'type', 'level', 'parent_id', 'child_id', 'write_date', 'has_image']}}

    def _pos_data_process(self, loaded_data):
        if loaded_data:
            branch_list = []
            res_company = self.env['res.company'].sudo().search([])
            for record in res_company:
                branch_list.append({
                    'id': record.id,
                    'name': record.name,
                })
            loaded_data['res_company_branch'] = branch_list
            cover_image = self.env['dn.cover.image'].search([], limit=1)
            if cover_image and cover_image.image:
                loaded_data['cover_image'] = cover_image.image
            else:
                loaded_data['cover_image'] = False
        result = super(POSSessionModelInherit, self)._pos_data_process(loaded_data)
        return result

    def _loader_params_res_partner(self):
        return {
            'search_params': {
                'domain': self._get_partners_domain(),
                'fields': [
                    'name', 'street', 'city', 'state_id', 'state', 'donor_type', 'country_id', 'vat', 'lang', 'phone', 'zip', 'mobile', 'email',
                    'barcode', 'write_date', 'property_account_position_id', 'property_product_pricelist', 'parent_name', 'cnic_no', 'donation_type', 
                    'bank_name', 'cheque_number', 'branch_id', 'is_donee', 'registration_category'
                ],
                # 'fields': [
                #     'name', 'street', 'city', 'state_id', 'country_id', 'vat', 'lang', 'phone', 'zip', 'mobile', 'email',
                #     'barcode', 'write_date', 'property_account_position_id', 'property_product_pricelist', 'parent_name',
                #     'reference_number', 'cnic_no', 'category', 'donation_type', 'amount', 'bank_name', 'cheque_number',
                #     'branch_id', 'delivery_charges_amount', 'donation_service'
                # ],
            },
        }
    
    # def _pos_ui_models_to_load(self):
    #     result = super()._pos_ui_models_to_load()
    #     result.append('dn.cover.image')
    #     return result
    
    # def _loader_params_dn_cover_image(self):
    #     return {
    #         'search_params': {
    #             'domain': [],
    #             'fields': ['image'],
    #         }
    #     }
    
    # def _get_pos_ui_dn_cover_image(self, params):
    #     cover = self.env['dn.cover.image'].search([], limit=1)
    #     return {
    #         'cover_image': cover.image.decode('utf-8') if cover and cover.image else False
    #     }
