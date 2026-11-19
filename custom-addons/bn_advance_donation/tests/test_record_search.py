# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestDonorRecordSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.donor_tag = ref('bn_profile_management.donor_partner_category')
        cls.donee_tag = ref('bn_profile_management.donee_partner_category')
        cls.individual_tag = ref('bn_profile_management.individual_partner_category')
        cls.account_tag = cls.env['res.partner.category']._record_search_program('donor_account')
        cls.user = cls.env['res.users'].create({
            'name': 'ad_rs_user', 'login': 'ad_rs_user', 'groups_id': [(6, 0, [
                ref('base.group_user').id,
                ref('bn_advance_donation.group_adv_don_root').id,
                ref('bn_profile_management.profile_management_user_group').id,
            ])]})
        cls.action = ref('bn_advance_donation.record_search_advance_donation_action')

    def _search(self, **values):
        """Run the menu's Record Search, then its confirmation, as the user."""
        context = safe_eval(self.action.context)
        wizard = self.env['record.search'].with_user(self.user).with_context(context).create(values)
        confirm_action = wizard.action_search()
        confirm = self.env['confirm.search'].with_user(self.user).with_context(
            confirm_action['context']).create({})
        return confirm.action_confirm()

    def test_programme_and_menu(self):
        self.assertTrue(self.account_tag)
        self.assertEqual(self.account_tag.name, 'Donor Account')
        self.assertEqual(self.account_tag.registration_role, 'donor')
        menu = self.env.ref('bn_advance_donation.advance_donation_profile_menu')
        self.assertIn(menu, self.account_tag.program_menu_ids)
        self.assertTrue(menu.active)
        self.account_tag.registration_program_active = False
        self.assertFalse(menu.active)

    def test_existing_donor_gets_donor_account(self):
        donor = self.env['res.partner'].create({
            'name': 'RS Donor', 'cnic_no': '42101-5555555-1',
            'category_id': [(6, 0, (self.donor_tag | self.individual_tag).ids)]})
        action = self._search(search_type='cnic_no', cnic_no='42101-5555555-1')
        self.assertEqual(action.get('res_id'), donor.id)
        self.assertIn(self.account_tag, donor.category_id)

        # searching again changes nothing
        tags = donor.category_id
        self.assertEqual(self._search(search_type='cnic_no', cnic_no='42101-5555555-1').get('res_id'), donor.id)
        self.assertEqual(donor.category_id, tags)

    def test_donee_becomes_donor(self):
        donee = self.env['res.partner'].create({
            'name': 'RS Donee', 'mobile': '3214445556',
            'category_id': [(6, 0, (self.donee_tag | self.individual_tag).ids)]})
        action = self._search(search_type='mobile_no', mobile_no='3214445556',
                              country_code_id=self.env.ref('base.pk').id)
        self.assertEqual(action.get('res_id'), donee.id)
        self.assertLessEqual(self.donor_tag | self.account_tag | self.donee_tag, donee.category_id)

    def test_donor_field_lists_donor_accounts_only(self):
        Partner = self.env['res.partner']
        donor_only = Partner.create({'name': 'RS Donor only', 'category_id': [(6, 0, self.donor_tag.ids)]})
        account_only = Partner.create({'name': 'RS Account only', 'category_id': [(6, 0, self.account_tag.ids)]})
        both = Partner.create({'name': 'RS Donor Account',
                               'category_id': [(6, 0, (self.donor_tag | self.account_tag).ids)]})
        Donation = self.env['advance.donation']
        domain = Donation._fields['donor_id'].get_domain_list(Donation)
        found = Partner.search(domain + [('id', 'in', (donor_only | account_only | both).ids)])
        self.assertEqual(found, both)

    def test_existing_donors_tagged_once(self):
        Partner = self.env['res.partner']
        with_donation = Partner.create({'name': 'RS Old Donor', 'category_id': [(6, 0, self.donor_tag.ids)]})
        with_receipt = Partner.create({'name': 'RS Old Receipt Donor'})
        unused = Partner.create({'name': 'RS Unused Donor', 'category_id': [(6, 0, self.donor_tag.ids)]})
        self.env['advance.donation'].create({'donor_id': with_donation.id})
        self.env['advance.donation.receipt'].create({'donor_id': with_receipt.id, 'amount': 10})

        params = self.env['ir.config_parameter'].sudo()
        params.set_param('bn_advance_donation.donor_account_tagged', False)
        self.env['res.partner.category']._setup_donor_account_program()
        for partner in (with_donation, with_receipt):
            self.assertLessEqual(self.donor_tag | self.account_tag, partner.category_id, partner.name)
        self.assertNotIn(self.account_tag, unused.category_id)

        # done once: a later upgrade does not give the tag back
        with_donation.category_id = [(3, self.account_tag.id)]
        self.env['res.partner.category']._setup_donor_account_program()
        self.assertNotIn(self.account_tag, with_donation.category_id)

    def test_donor_account_is_a_tag_not_a_registered_programme(self):
        welfare = self.env.ref('bn_profile_management.welfare_partner_category')
        partner = self.env['res.partner'].create({
            'name': 'RS Both Roles',
            'category_id': [(6, 0, (self.donor_tag | self.account_tag | self.donee_tag | welfare).ids)]})
        self.assertIn(self.account_tag, partner.category_id)
        self.assertEqual(partner.registered_program_ids, welfare)
        self.assertEqual(partner.registered_program_count, 1)

    def test_donors_menu_lists_donor_accounts(self):
        Partner = self.env['res.partner']
        donor_only = Partner.create({'name': 'RS Menu Donor only', 'category_id': [(6, 0, self.donor_tag.ids)]})
        both = Partner.create({'name': 'RS Menu Donor Account',
                               'category_id': [(6, 0, (self.donor_tag | self.account_tag).ids)]})
        action = self.env.ref('bn_advance_donation.advance_donation_donor_action')
        found = Partner.with_user(self.user).search(
            safe_eval(action.domain) + [('id', 'in', (donor_only | both).ids)])
        self.assertEqual(found, both)
        menu = self.env.ref('bn_advance_donation.advance_donation_donor_menu')
        self.assertEqual(menu.parent_id, self.env.ref('bn_advance_donation.advance_donation_profile_menu'))

    def test_no_match_opens_a_new_donor(self):
        action = self._search(search_type='cnic_no', cnic_no='42101-9999999-9')
        self.assertFalse(action.get('res_id'))
        tag_ids = action['context']['default_category_id'][0][2]
        self.assertEqual(set(tag_ids), set((self.donor_tag | self.account_tag | self.individual_tag).ids))
        self.assertEqual(action['context']['default_cnic_no'], '42101-9999999-9')
