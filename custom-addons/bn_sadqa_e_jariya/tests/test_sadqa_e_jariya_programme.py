# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSadqaEJariyaProgramme(TransactionCase):
    """Sadqa e Jariya is its own programme, apart from Welfare."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.sadqa = ref('bn_sadqa_e_jariya.sadqa_e_jariya_partner_category')
        cls.welfare = ref('bn_profile_management.welfare_partner_category')
        cls.donee = ref('bn_profile_management.donee_partner_category')
        cls.institute = ref('bn_profile_management.coorporate_institute_partner_category')
        cls.individual = ref('bn_profile_management.individual_partner_category')
        cls.Welfare = cls.env['welfare']

    def test_record_search_of_sadqa_e_jariya(self):
        action = self.env.ref('bn_sadqa_e_jariya.sadqa_e_jariya_record_search_action')
        context = dict(eval(action.context))
        wizard = self.env['record.search'].with_context(**context).create({'search_type': 'cnic_no'})
        self.assertEqual(wizard.program_id, self.sadqa)
        self.assertEqual(wizard.category, 'institution')
        confirm = self.env['confirm.search'].create({
            'registration_type': 'donee', 'search_type': 'cnic_no', 'cnic_no': '42101-4000001-1',
            'program_id': wizard.program_id.id, 'category': wizard.category})
        tags = confirm.action_confirm()['context']['default_category_id'][0][2]
        self.assertEqual(set(tags), {self.donee.id, self.institute.id, self.sadqa.id})
        self.assertNotIn(self.welfare.id, tags, 'not a Welfare donee')

    def test_registering_creates_the_institution_application(self):
        partner = self.env['res.partner'].create({
            'name': 'Masjid Noor', 'mobile': '3001400001', 'cnic_no': '42101-4000002-1',
            'category_id': [(6, 0, (self.donee | self.institute | self.sadqa).ids)]})
        partner.action_register()
        application = self.Welfare.search([('donee_id', '=', partner.id)])
        self.assertEqual(len(application), 1)
        self.assertFalse(application.is_individual)
        self.assertEqual(partner.registered_program_ids, self.sadqa)

    def test_existing_institution_donees_get_their_tag(self):
        """Before: tagged Welfare. Institutions with a Sadqa e Jariya
        application move to its tag; Welfare stays when they also have an
        individual Welfare application."""
        old = self.env['res.partner'].create({
            'name': 'Old Madrasa', 'mobile': '3001400002',
            'category_id': [(6, 0, (self.donee | self.institute | self.welfare).ids)]})
        both = self.env['res.partner'].create({
            'name': 'Both', 'mobile': '3001400003',
            'category_id': [(6, 0, (self.donee | self.institute | self.welfare).ids)]})
        imported = self.env['res.partner'].create({'name': 'Fetched', 'mobile': '3001400004',
                                                   'category_id': [(6, 0, self.welfare.ids)]})
        self.Welfare.create([{'donee_id': old.id, 'is_individual': False},
                             {'donee_id': both.id, 'is_individual': False},
                             {'donee_id': both.id, 'is_individual': True},
                             {'donee_id': imported.id, 'is_individual': False}])
        self.env['res.partner']._setup_sadqa_e_jariya_donees()
        self.assertEqual(old.category_id, self.donee | self.institute | self.sadqa)
        self.assertEqual(both.category_id, self.donee | self.institute | self.welfare | self.sadqa)
        self.assertEqual(imported.category_id, self.donee | self.institute | self.sadqa,
                         'contacts fetched from the portal get Donee and Institute too')
        self.assertEqual(both.registered_program_count, 2)

    def test_donee_menu_lists_sadqa_e_jariya_donees(self):
        action = self.env.ref('bn_sadqa_e_jariya.sadqa_e_jariya_donee_action')
        domain = eval(action.domain)
        sadqa_donee = self.env['res.partner'].create({
            'name': 'Listed', 'mobile': '3001400005',
            'category_id': [(6, 0, (self.donee | self.institute | self.sadqa).ids)]})
        welfare_donee = self.env['res.partner'].create({
            'name': 'Not listed', 'mobile': '3001400006',
            'category_id': [(6, 0, (self.donee | self.individual | self.welfare).ids)]})
        found = self.env['res.partner'].search(domain + [('id', 'in', (sadqa_donee | welfare_donee).ids)])
        self.assertEqual(found, sadqa_donee)
