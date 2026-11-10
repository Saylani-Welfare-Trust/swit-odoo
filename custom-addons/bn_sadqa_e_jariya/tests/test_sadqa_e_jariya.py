# -*- coding: utf-8 -*-
import datetime

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSadqaEJariya(TransactionCase):
    """Sadqa e Jariya on the current code base: a Record Search programme of
    the dynamic profile (tags added, never replaced; one contact per person),
    its own profile popup, the tier access structure and the search views."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.tag = ref('bn_sadqa_e_jariya.sadqa_jariya_partner_category')
        cls.donee = ref('bn_profile_management.donee_partner_category')
        cls.institute = ref('bn_profile_management.coorporate_institute_partner_category')
        cls.welfare = ref('bn_profile_management.welfare_partner_category')
        cls.individual = ref('bn_profile_management.individual_partner_category')
        cls.area = cls.env['sadqa.jariya.area'].create({'name': 'Test Area'})

        def user(login, *groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [ref('base.group_user').id] + [ref(g).id for g in groups])]})
        cls.user = user('sq_user', 'bn_sadqa_e_jariya.group_institutional_disbursement')
        cls.auditor = user('sq_audit', 'bn_sadqa_e_jariya.sadqa_e_jariya_audit_group')
        cls.admin = user('sq_admin', 'bn_sadqa_e_jariya.sadqa_e_jariya_admin_group')
        cls.cashier = user('sq_pos', 'bn_sadqa_e_jariya.group_sadqa_jariya_pos_action')
        cls.employee = user('sq_none')

    def _institution(self, name):
        """A registered Sadqa e Jariya donee (Donee, Corporate / Institute, Sadqa-e-Jaria)"""
        partner = self.env['res.partner'].create({
            'name': name, 'category_id': [(6, 0, (self.donee | self.institute | self.tag).ids)]})
        partner.state = 'register'
        return partner

    def _search(self, **vals):
        wizard = self.env['confirm.search'].create(dict({
            'registration_type': 'donee', 'search_type': 'mobile_no', 'program_id': self.tag.id,
            'country_code_id': self.env.ref('base.pk').id}, **vals))
        return wizard, wizard.action_confirm()

    # ------------------------------------------------------------------
    def test_programme_configured(self):
        Tag = self.env['res.partner.category']
        self.assertEqual(Tag._record_search_program('sadqa_e_jariya'), self.tag)
        self.assertEqual((self.tag.registration_role, self.tag.registration_kind), ('donee', 'institution'))
        self.assertEqual(set(self.tag.registration_required_field_ids.mapped('name')),
                         {'mobile', 'street', 'city', 'cnic_no', 'date_of_birth', 'nearest_land_mark'})
        # the menu presets the programme
        wizard = self.env['record.search'].with_context(
            default_program_code='sadqa_e_jariya', default_program_locked=True).create({'search_type': 'mobile_no'})
        self.assertEqual(wizard.program_id, self.tag)

    def test_new_institution_from_record_search(self):
        _wizard, action = self._search(mobile_no='03001110001')
        self.assertEqual(action['view_id'], self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form').id)
        self.assertTrue(action['context']['sadqa_jariya_profile'])
        tags = set(action['context']['default_category_id'][0][2])
        self.assertEqual(tags, {self.donee.id, self.institute.id, self.tag.id})
        partner = self.env['res.partner'].with_context(**action['context']).create({'name': 'Masjid Test'})
        self.assertTrue(partner.is_sadqa_jariya_donee)
        self.assertEqual(partner.mobile, '3001110001')

    def test_existing_person_keeps_other_programmes(self):
        """A Welfare donee applying for Sadqa e Jariya: the same contact, its
        tags are added (Welfare stays), and it now counts two programmes."""
        person = self.env['res.partner'].create({
            'name': 'Welfare Person', 'mobile': '3001110002', 'country_code_id': self.env.ref('base.pk').id,
            'category_id': [(6, 0, (self.donee | self.individual | self.welfare).ids)],
            'date_of_birth': datetime.date(1980, 1, 1)})
        count = self.env['res.partner'].search_count([])
        _wizard, action = self._search(mobile_no='0300-1110002')
        self.assertEqual(action['res_id'], person.id)
        self.assertEqual(self.env['res.partner'].search_count([]), count, 'no second contact')
        self.assertTrue({self.welfare, self.tag, self.donee} <= set(person.category_id))
        self.assertEqual(person.registered_program_ids, self.welfare | self.tag)
        self.assertEqual(person.registered_program_count, 2)

    def test_register_requires_institution_fields(self):
        partner = self.env['res.partner'].create({
            'name': 'Madrasa Test', 'mobile': '3001110003', 'country_code_id': self.env.ref('base.pk').id,
            'category_id': [(6, 0, (self.donee | self.institute | self.tag).ids)]})
        self.assertIn(',nearest_land_mark,', partner.profile_required_field_names)
        with self.assertRaises(ValidationError):
            partner.action_register()
        partner.write({'sadqa_contact_person': 'Imam', 'sadqa_area_id': self.area.id, 'street': 'Street 1',
                       'city': 'Karachi', 'cnic_no': '42101-1110003-1', 'nearest_land_mark': 'Park',
                       'date_of_birth': datetime.date(2010, 1, 1)})
        with self.assertRaises(ValidationError, msg='the manager must be 18'):
            partner.action_register()

    def test_profile_form_views(self):
        Partner = self.env['res.partner']
        for xmlid in ('bn_profile_management.profile_management_view_form',
                      'bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form'):
            arch = etree.fromstring(Partner.get_views([(self.env.ref(xmlid).id, 'form')])['views']['form']['arch'])
            contact = arch.xpath('//field[@name="sadqa_contact_person"]')
            self.assertTrue(contact, xmlid)
            # a person's details are kept off an institution, on top of the tag rule
            gender = arch.xpath('//notebook//field[@name="gender"]')[0]
            self.assertIn('is_sadqa_jariya_donee', gender.get('invisible'))
            self.assertIn('profile_visible_form_field_names', gender.get('invisible'))
            # required by the Sadqa-e-Jaria tag until registered
            landmark = arch.xpath('//field[@name="nearest_land_mark"]')[0]
            self.assertIn("',nearest_land_mark,' in (profile_required_field_names or '')", landmark.get('required'))
        popup = etree.fromstring(Partner.get_views(
            [(self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form').id, 'form')])['views']['form']['arch'])
        self.assertTrue(popup.xpath('//footer/button[@name="action_sadqa_profile_save"]'))
        # Send Profile Form is for Sadqa e Jariya users only
        for user, shown in ((self.user, True), (self.employee, False)):
            arch = etree.fromstring(Partner.with_user(user).get_views(
                [(self.env.ref('bn_profile_management.profile_management_view_form').id, 'form')])['views']['form']['arch'])
            self.assertEqual(bool(arch.xpath('//button[@name="action_send_sadqa_profile_form"]')), shown, user.login)

    def test_access_tiers(self):
        donee = self._institution('Access Masjid')
        application = self.env['sadqa.jariya'].with_user(self.user).create({'donee_id': donee.id})
        application.with_user(self.user).write({'hod_remarks': 'ok'})
        self.assertEqual(application.with_user(self.auditor).read(['name'])[0]['id'], application.id)
        with self.assertRaises(AccessError):
            application.with_user(self.auditor).write({'hod_remarks': 'no'})
        with self.assertRaises(AccessError):
            self.env['sadqa.jariya'].with_user(self.employee).search([])
        with self.assertRaises(AccessError):
            application.with_user(self.user).unlink()
        with self.assertRaises(AccessError):
            self.env['sadqa.jariya.area'].with_user(self.user).create({'name': 'X'})
        self.env['sadqa.jariya.area'].with_user(self.admin).create({'name': 'Admin Area'})
        # the cashier disburses lines at the POS
        line = self.env['sadqa.jariya.line'].create({'application_id': application.id, 'collection_point': 'bank'})
        line.with_user(self.cashier).action_disbursed()
        self.assertEqual(line.state, 'disbursed')
        # tiers: Administrator = Manager + Audit; Manager = User
        admin_groups = self.admin.groups_id
        self.assertIn(self.env.ref('bn_sadqa_e_jariya.group_institutional_disbursement'), admin_groups)
        self.assertIn(self.env.ref('bn_sadqa_e_jariya.sadqa_e_jariya_audit_group'), admin_groups)
        self.assertNotIn(self.env.ref('bn_sadqa_e_jariya.sadqa_e_jariya_root_group'), admin_groups,
                         'the Menu group is given explicitly')

    def test_search_views_and_form_tabs(self):
        for model, xmlid in (('sadqa.jariya', 'sadqa_jariya_view_search'),
                             ('sadqa.jariya.line', 'sadqa_jariya_line_view_search'),
                             ('sadqa.jariya.recurring.line', 'sadqa_jariya_recurring_line_view_search'),
                             ('sadqa.jariya.fetch.log', 'sadqa_jariya_fetch_log_view_search')):
            view = self.env.ref('bn_sadqa_e_jariya.' + xmlid)
            self.assertTrue(self.env[model].get_views([(view.id, 'search')])['views']['search']['arch'])
        donee = self._institution('Form Masjid')
        with_form, without = self.env['sadqa.jariya'].create([{'donee_id': donee.id}, {'donee_id': donee.id}])
        form = self.env['sadqa.jariya.form'].create({
            'application_id': with_form.id, 'submission': 'donee', 'md_number': 'MD-1'})
        self.assertEqual(with_form.donee_form_id, form)
        self.assertEqual(with_form.donee_form_md_number, 'MD-1')
        Application = self.env['sadqa.jariya']
        self.assertIn(with_form, Application.search([('donee_form_id', '=', form.id)]))
        found = Application.search([('id', 'in', (with_form | without).ids), ('donee_form_id', '=', False)])
        self.assertEqual(found, without)
        # editing the form updates the tab
        form.md_number = 'MD-2'
        self.assertEqual(with_form.donee_form_md_number, 'MD-2')

    def test_role_steps_need_their_role(self):
        """HOD / Committee / Member steps are refused to a plain User, even over RPC."""
        hod = self.env['res.users'].create({
            'name': 'sq_hod', 'login': 'sq_hod',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('bn_sadqa_e_jariya.group_sadqa_jariya_hod').id])]})
        application = self.env['sadqa.jariya'].create({
            'donee_id': self._institution('Role Masjid').id, 'hod_remarks': 'ok'})
        application.state = 'hod_approve'
        for method in ('action_move_to_committee', 'action_committee_decision', 'action_approve'):
            with self.assertRaises(UserError, msg=method):
                getattr(application.with_user(self.user), method)()
        self.assertTrue(hod.has_group('bn_sadqa_e_jariya.group_institutional_disbursement'), 'HOD implies User')
        application.with_user(hod).action_move_to_committee()
        self.assertEqual(application.state, 'committee_approval')
