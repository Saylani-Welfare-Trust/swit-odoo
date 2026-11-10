# -*- coding: utf-8 -*-
from odoo import api, models

SADQA_TAG = 'bn_sadqa_e_jariya.sadqa_e_jariya_partner_category'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _is_sadqa_e_jariya_donee(self):
        tag = self.env.ref(SADQA_TAG, raise_if_not_found=False)
        return bool(tag and tag in self.category_id)

    def _register_one(self):
        """A Sadqa e Jariya donee gets its institution application when
        registered, as Welfare donees get theirs."""
        result = super()._register_one()
        if self._is_sadqa_e_jariya_donee() and 'Welfare' not in self.category_id.mapped('name'):
            self.action_welfare_application()
        return result

    @api.model
    def _setup_sadqa_e_jariya_donees(self):
        """Contacts used as donee on an institution disbursement (Sadqa e
        Jariya) carry its tag, with Donee and Corporate / Institute. Before
        Sadqa e Jariya had its own tag they were tagged Welfare: that tag is
        removed when the contact has no individual Welfare application.
        Idempotent; runs on every install / upgrade."""
        ref = self.env.ref
        tag = ref(SADQA_TAG, raise_if_not_found=False)
        if not tag:
            return
        Welfare = self.env['welfare'].sudo().with_context(active_test=False)
        donees = Welfare.search([('is_individual', '=', False), ('donee_id', '!=', False)]).donee_id
        if not donees:
            return
        individual = set(Welfare.search([('is_individual', '=', True), ('donee_id', 'in', donees.ids)]).donee_id.ids)
        welfare_tag = ref('bn_profile_management.welfare_partner_category')
        wanted = tag | ref('bn_profile_management.donee_partner_category') \
            | ref('bn_profile_management.coorporate_institute_partner_category')
        for partner in donees.sudo():
            commands = [(4, t.id) for t in wanted - partner.category_id]
            if welfare_tag in partner.category_id and partner.id not in individual:
                commands.append((3, welfare_tag.id))
            if commands:
                partner._profile_write({'category_id': commands})


class UserProfileReport(models.AbstractModel):
    _inherit = 'report.bn_profile_management.user_profile_report'

    def _get_welfare(self, partners, data):
        """A Sadqa e Jariya donee prints the welfare form of its latest
        institution application, as it did when it carried the Welfare tag."""
        if not data.get('welfare_id') and partners and partners[:1]._is_sadqa_e_jariya_donee():
            Welfare = self.env['welfare'].sudo()
            return Welfare.search([('donee_id', '=', partners[:1].id)], order='id desc', limit=1), True
        return super()._get_welfare(partners, data)
