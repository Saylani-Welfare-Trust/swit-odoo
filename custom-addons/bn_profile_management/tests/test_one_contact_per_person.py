# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError

from odoo.tests import tagged

from .test_profile_management import ProfileCase


@tagged('post_install', '-at_install')
class TestOneContactPerPerson(ProfileCase):
    """A person has one contact (CNIC, mobile + phone code, Registration ID),
    whichever module, screen or action creates it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.person = cls._donee_cls('Existing Person', mobile='3001500001', cnic_no='42101-5000001-1')

    @classmethod
    def _donee_cls(cls, name, **vals):
        values = {'name': name, 'category_id': [(6, 0, [cls.donee.id, cls.individual.id])]}
        values.update(vals)
        return cls.env['res.partner'].create(values)

    def test_plain_contact_with_the_same_mobile_refused(self):
        """Also contacts without any profile tag (Contacts app, other modules)."""
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.Partner.create({'name': 'Second Contact', 'mobile': '3001500001'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.Partner.create({'name': 'Same CNIC', 'cnic_no': '42101-5000001-1'})
        other_country = self.Partner.create({'name': 'Abroad', 'mobile': '3001500001',
                                             'country_code_id': self.env.ref('base.ae').id})
        self.assertTrue(other_country, 'same number with another phone code is another person')

    def test_child_contacts_may_repeat_the_company_number(self):
        company = self.Partner.create({'name': 'Trust Ltd', 'is_company': True, 'mobile': '3001500002'})
        child = self.Partner.create({'name': 'Accounts', 'parent_id': company.id, 'mobile': '3001500002'})
        self.assertEqual(child.parent_id, company)

    def test_find_or_create_reuses_the_person(self):
        Partner = self.Partner
        self.assertEqual(Partner._find_person(mobile='0300-1500001'), self.person)
        self.assertEqual(Partner._find_person(mobile='+92 300 1500001'), self.person)
        self.assertEqual(Partner._find_person(cnic='42101-5000001-1'), self.person)
        count = Partner.search_count([])
        found = Partner._find_or_create_person({'name': 'Typed Again', 'mobile': '03001500001'}, tags=self.donor)
        self.assertEqual(found, self.person)
        self.assertEqual(Partner.search_count([]), count, 'no second contact')
        self.assertIn(self.donor, self.person.category_id, 'the new role is added as a tag')
        self.assertEqual(self.person.name, 'Existing Person', 'the existing contact is not overwritten')

    def test_pos_create_customer_reuses_the_person(self):
        count = self.Partner.search_count([])
        partner_id = self.Partner.create_from_ui({
            'name': 'Walk-in', 'mobile': '3001500001', 'country_code_id': self.env.ref('base.pk').id,
            'donor_type': 'individual'})
        self.assertEqual(partner_id, self.person.id)
        self.assertEqual(self.Partner.search_count([]), count)
        self.assertIn(self.donor, self.person.category_id)
        new_id = self.Partner.create_from_ui({'name': 'New Walk-in', 'mobile': '3001500009',
                                              'donor_type': 'individual'})
        self.assertNotEqual(new_id, self.person.id)

    def test_employee_who_is_already_a_contact(self):
        employee = self.env['hr.employee'].create({'name': 'Staff Donee', 'mobile_phone': '0300-1500001'})
        self.assertEqual(employee.work_contact_id, self.person)
        self.assertIn(self.employee, self.person.category_id)
        fresh = self.env['hr.employee'].create({'name': 'New Staff', 'mobile_phone': '3001500010'})
        self.assertNotEqual(fresh.work_contact_id, self.person)

    def test_record_search_by_mobile_as_typed(self):
        action = self.env['confirm.search'].create({
            'registration_type': 'donee', 'search_type': 'mobile_no', 'mobile_no': '0300-1500001',
            'country_code_id': self.env.ref('base.pk').id, 'program_id': self.medical.id}).action_confirm()
        self.assertEqual(action['res_id'], self.person.id)

    def test_registration_id_belongs_to_one_contact(self):
        self.person.with_context(skip_profile_lock=True).sudo().write({'primary_registration_id': 'REG-T-0001'})
        other = self._donee_cls('Other Person', mobile='3001500003')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            other.sudo().write({'primary_registration_id': 'REG-T-0001'})
        self.assertEqual(self.Partner._find_person(registration_id='REG-T-0001'), self.person)
