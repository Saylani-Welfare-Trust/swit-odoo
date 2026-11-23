# -*- coding: utf-8 -*-
"""Record Search for programmes (from the Development branch). Used only when
a menu passes a programme code (default_program_code, e.g. Sadqa e Jariya);
Welfare, Microfinance, Medical and Student registration keep the existing
Record Search of this module unchanged."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ROLE_CATEGORY = {
    'donee': 'bn_profile_management.donee_partner_category',
    'donor': 'bn_profile_management.donor_partner_category',
}


class RecordSearch(models.TransientModel):
    _inherit = 'record.search'

    # no length limit: size=10 cut "0300-1234567" to "0300-12345" before the search
    mobile_no = fields.Char('Mobile No.', size=None)

    program_id = fields.Many2one(
        'res.partner.category', string='Register For',
        domain="[('registration_program_code', '!=', False), ('registration_program_active', '=', True), "
               "('registration_role', '=', registration_type)]")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = self.env.context.get('default_program_code')
        if not code:
            return res
        program = self.env['res.partner.category']._record_search_program(code)
        if not program:
            raise UserError(_('No tag has the Record Search code "%s": set it on the programme tag '
                              '(Contacts > Configuration > Tags).') % code)
        if not program.registration_program_active:
            raise UserError(_('The programme "%s" is disabled: enable it on its tag.') % program.name)
        res.update({'program_id': program.id, 'registration_type': program.registration_role,
                    'program_locked': True, 'donee_registration_type': False})
        if program.registration_kind in ('individual', 'institution'):
            res['category'] = program.registration_kind
            res['program_kind'] = program.registration_kind
        return res

    def action_search(self):
        action = super().action_search()
        if self.program_id:
            action['context']['default_program_id'] = self.program_id.id
        return action


class ConfirmSearch(models.TransientModel):
    _inherit = 'confirm.search'

    mobile_no = fields.Char('Mobile No.', size=None)

    program_id = fields.Many2one('res.partner.category', string='Register For')

    # ------------------------------------------------------------------
    def _program(self):
        return self.program_id

    def _search_domain(self):
        if self.search_type == 'registration_id':
            if not self.registration_id:
                raise UserError(_('Please enter the Registration ID to search for.'))
            code = self.registration_id.strip()
            return ['|', ('primary_registration_id', '=', code), ('secondary_registration_id', '=', code)]
        if self.search_type == 'cnic_no':
            if not self.cnic_no:
                raise UserError(_('Please enter the CNIC No. to search for.'))
            return [('cnic_no', '=', self.cnic_no)]
        if not self.mobile_no:
            raise UserError(_('Please enter the Mobile No. to search for.'))
        domain = [('mobile', '=', self.env['res.partner']._normalize_mobile(self.mobile_no))]
        if self.country_code_id:
            domain.append(('country_code_id', '=', self.country_code_id.id))
        return domain

    def _kind_tag(self):
        ref = self.env.ref
        program = self._program()
        institution = (program.registration_kind == 'institution'
                       or (program.registration_kind != 'individual' and self.category == 'institution'))
        return (ref('bn_profile_management.coorporate_institute_partner_category') if institution
                else ref('bn_profile_management.individual_partner_category'))

    def _search_tags(self):
        """Role and programme tags: every contact found or created gets them."""
        return self.env.ref(ROLE_CATEGORY[self.registration_type]) | self._program()

    def _category_ids(self):
        """Tags of a new profile: role, Individual / Corporate-Institute, programme."""
        return (self._search_tags() | self._kind_tag()).ids

    def _add_search_tags(self, partners):
        """An existing person taking a new programme: ADD the tags, never
        replace the ones the person already has."""
        for partner in partners:
            missing = self._search_tags() - partner.category_id
            if missing:
                partner.sudo().write({'category_id': [(4, tag.id) for tag in missing]})

    def _form_action(self, partner=None):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
            'target': 'new',
            'context': {'from_record_search': True},
        }
        if partner:
            action['res_id'] = partner.id
            return action
        action['context'].update({
            'default_category_id': [(6, 0, self._category_ids())],
            'default_country_code_id': (self.country_code_id or self.env.ref('base.pk')).id,
        })
        if self.cnic_no:
            action['context']['default_cnic_no'] = self.cnic_no
        if self.mobile_no:
            action['context']['default_mobile'] = self.env['res.partner']._normalize_mobile(self.mobile_no)
        return action

    # ------------------------------------------------------------------
    def action_confirm(self):
        if not self.program_id:
            return super().action_confirm()
        self.ensure_one()
        if not self.program_id.registration_program_active:
            raise UserError(_('The programme "%s" is disabled.') % self.program_id.name)
        # one contact per person: every contact, whatever its tags
        matches = self.env['res.partner'].search(self._search_domain())
        if len(matches) > 1:
            raise ValidationError(_('%(count)s contacts match this search (%(names)s): merge them first '
                                    '(Contacts, select them, Action > Merge), then search again.') % {
                'count': len(matches), 'names': ', '.join(matches.mapped('display_name'))})
        if matches:
            self._add_search_tags(matches)
        return self._form_action(matches or None)
