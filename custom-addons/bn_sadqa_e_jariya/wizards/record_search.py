from odoo import api, models

SADQA_TAG = 'bn_sadqa_e_jariya.sadqa_jariya_partner_category'
# Asked of an institution before it is registered (the profile form shows and requires them);
# the contact person and area are Sadqa e Jariya's own fields, required by its view
REQUIRED_TO_REGISTER = ('mobile', 'street', 'city', 'cnic_no', 'date_of_birth', 'nearest_land_mark')


class ConfirmSearch(models.TransientModel):
    """Sadqa e Jariya is a Record Search programme (its tag has the code
    sadqa_e_jariya, Donee, Corporate / Institute): the search adds the tags,
    never replacing the person's others. The profile opens in Sadqa e
    Jariya's own popup (Save keeps it open, Send Profile Form)."""
    _inherit = 'confirm.search'

    def _is_sadqa_e_jariya(self):
        tag = self.env.ref(SADQA_TAG, raise_if_not_found=False)
        return bool(tag) and self._program() == tag

    def _form_action(self, partner=None):
        action = super()._form_action(partner)
        if self._is_sadqa_e_jariya():
            action['view_id'] = self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form').id
            action['context']['sadqa_jariya_profile'] = True
        return action


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    @api.model
    def _setup_sadqa_e_jariya_programme(self):
        """Every install / upgrade: the Sadqa-e-Jaria tag is the Record Search
        programme of Sadqa e Jariya, with the fields an institution needs to
        register (only set when not configured yet, an administrator's changes
        are kept)."""
        tag = self.env.ref(SADQA_TAG, raise_if_not_found=False)
        if not tag:
            return
        if not tag.registration_program_code and not self._record_search_program('sadqa_e_jariya'):
            tag.write({'registration_program_code': 'sadqa_e_jariya', 'registration_role': 'donee',
                       'registration_kind': 'institution'})
        if not tag.registration_required_field_ids:
            fields = self.env['ir.model.fields'].sudo().search([
                ('model', '=', 'res.partner'), ('name', 'in', REQUIRED_TO_REGISTER)])
            tag.write({'registration_required_field_ids': [(6, 0, fields.ids)]})
