from odoo import models, fields


class RecordSearch(models.TransientModel):
    _inherit = 'record.search'

    donee_registration_type = fields.Selection(selection_add=[('sadqa_e_jariya', 'Sadqa-e-Jaria')], ondelete={'sadqa_e_jariya': 'set null'})
    is_sadqa_e_jariya = fields.Boolean('Is Sadqa e Jariya')

    def action_search(self):
        action = super().action_search()
        action['context']['is_sadqa_e_jariya'] = self.is_sadqa_e_jariya
        return action


class ConfirmSearch(models.TransientModel):
    _inherit = 'confirm.search'

    donee_registration_type = fields.Selection(selection_add=[('sadqa_e_jariya', 'Sadqa-e-Jaria')], ondelete={'sadqa_e_jariya': 'set null'})

    def _sadqa_jariya_tags(self):
        """Donee, Corporate / Institute and Sadqa-e-Jaria: Sadqa e Jariya registers institutions only"""
        return [(6, 0, [
            self.env.ref('bn_profile_management.donee_partner_category').id,
            self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
            self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_partner_category').id,
        ])]

    def return_donee_form(self, donee=None):
        if self.donee_registration_type != 'sadqa_e_jariya':
            return super().return_donee_form(donee)
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form').id,
            'domain': '[("category_id.name", "in", ["Donee"])]',
            'target': 'new',
            'context': {'from_record_search': True, 'sadqa_jariya_profile': True},
        }
        if donee:
            donee.category_id = self._sadqa_jariya_tags()
            action['res_id'] = donee.id
        else:
            action['context'].update({
                'default_category_id': self._sadqa_jariya_tags(),
                'default_cnic_no': self.cnic_no,
                'default_mobile': self.mobile_no,
                'default_country_code_id': self.country_code_id.id,
            })
        return action
