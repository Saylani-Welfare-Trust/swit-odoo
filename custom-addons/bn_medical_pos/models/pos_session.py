import hashlib
import json

from odoo import _, models
from odoo.exceptions import AccessError
from odoo.osv import expression

# Patients loaded when the POS opens (the most recently registered ones), the others come from the search
MEDICAL_PATIENTS_PRELOAD = 200


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_category(self):
        params = super()._loader_params_pos_category()
        if self.config_id.is_medical_pos:
            categories = self.config_id._mh_pos_categories()
            if categories:
                params['search_params']['domain'] = [('id', 'in', categories.ids)]
        return params

    def mh_load_catalog(self, stamp=False, stamp_only=False):
        """Categories and products of an open Medical & Health counter, to refresh it after a change.

        :param stamp: the stamp of what the counter shows: nothing else is returned if it is still the same
        """
        self._mh_check_access()
        category_params = self._loader_params_pos_category()['search_params']
        categories = self.env['pos.category'].search_read(category_params['domain'], category_params['fields'])
        products = self.env['product.product'].search_read(
            self.config_id._get_available_product_domain(), ['pos_categ_ids'], order='id')
        new_stamp = hashlib.sha1(json.dumps([
            [(category['id'], category['name'], category['parent_id'] and category['parent_id'][0]) for category in categories],
            [(product['id'], product['pos_categ_ids']) for product in products],
        ]).encode()).hexdigest()
        if stamp_only or stamp == new_stamp:
            return {'stamp': new_stamp, 'changed': stamp != new_stamp}
        return {'stamp': new_stamp, 'changed': True, 'categories': categories, 'products': products}

    def _loader_params_res_partner(self):
        params = super()._loader_params_res_partner()
        fields_list = params['search_params']['fields']
        extra = ['mobile', 'cnic_no', 'primary_registration_id', 'date_of_birth']
        params['search_params']['fields'] = list(dict.fromkeys(fields_list + extra))
        return params

    # ------------------------------------------------------------------
    # On a Medical & Health POS the customers are the patients.
    # Cashiers usually have no rights on donee profiles (see edit_donor_rule),
    # so the patients are read as superuser, limited to the patient domain.
    # ------------------------------------------------------------------

    def _mh_check_access(self):
        self.ensure_one()
        if not self.config_id.is_medical_pos:
            raise AccessError(_("%s isn't a Medical & Health POS.", self.config_id.name))
        # the session is given by id from the client: it must be one this user can see
        self.check_access_rule('read')

    def _mh_patient_pos_data(self, partners):
        """Partners as the POS loads them"""
        return partners.sudo().read(self._loader_params_res_partner()['search_params']['fields'])

    def _get_pos_ui_res_partner(self, params):
        if not self.config_id.is_medical_pos:
            return super()._get_pos_ui_res_partner(params)
        return self.env['res.partner'].sudo().search_read(
            self.env['res.partner']._mh_patient_domain(),
            params['search_params']['fields'],
            limit=MEDICAL_PATIENTS_PRELOAD,
            order='id desc',
        )

    def get_pos_ui_res_partner_by_params(self, custom_search_params):
        if len(self) != 1 or not self.config_id.is_medical_pos:
            return super().get_pos_ui_res_partner_by_params(custom_search_params)
        self._mh_check_access()
        loader_params = self._loader_params_res_partner()['search_params']
        search_params = {**loader_params, **custom_search_params}
        search_params['fields'] = loader_params['fields']
        search_params['domain'] = expression.AND([
            search_params.get('domain') or [],
            self.env['res.partner']._mh_patient_domain(),
        ])
        return self.env['res.partner'].sudo().search_read(**search_params)

    def mh_search_patients(self, term='', limit=30, offset=0):
        """Patients matching the term on name, mobile, CNIC or registration ID"""
        self._mh_check_access()
        Partner = self.env['res.partner']
        patients = Partner.sudo().search(
            Partner._mh_patient_search_domain(term),
            limit=limit, offset=offset, order='name, id' if (term or '').strip() else 'id desc')
        return self._mh_patient_pos_data(patients)

    def mh_register_patient(self, vals):
        """Register a patient from the customer screen of the POS"""
        self._mh_check_access()
        patient, existing = self.env['res.partner']._mh_register_patient(vals)
        return {'existing': existing, 'partner': self._mh_patient_pos_data(patient)[0]}
