# -*- coding: utf-8 -*-
import datetime

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.api import call_kw
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


class ProfileCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = lambda x: cls.env.ref('bn_profile_management.' + x)
        cls.donee, cls.donor, cls.individual = ref('donee_partner_category'), ref('donor_partner_category'), ref('individual_partner_category')
        cls.employee, cls.medical, cls.welfare = ref('employee_partner_category'), ref('medical_partner_category'), ref('welfare_partner_category')
        cls.Partner = cls.env['res.partner']
        cls.clerk = cls.env['res.users'].create({
            'name': 'Profile Clerk', 'login': 'profile_clerk',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, ref('profile_management_user_group').id])],
        })

    def _donee(self, name, **vals):
        values = {'name': name, 'category_id': [(6, 0, [self.donee.id, self.individual.id])],
                  'date_of_birth': datetime.date(1990, 1, 1), 'gender': 'male'}
        values.update(vals)
        return self.Partner.create(values)


@tagged('post_install', '-at_install')
class TestProfileManagement(ProfileCase):

    def test_donees_without_cnic_are_not_duplicates(self):
        first = self._donee('No CNIC 1', mobile='3001000001', has_cnic='no')
        second = self._donee('No CNIC 2', mobile='3001000002', has_cnic='no')
        first.action_register()
        second.action_register()
        self.assertEqual(second.state, 'register')

    def test_real_duplicate_still_blocked(self):
        self._donee('Dup 1', mobile='3001000003', cnic_no='42101-1000003-1').action_register()
        with self.assertRaises(ValidationError):
            self._donee('Dup 2', mobile='3001000004', cnic_no='42101-1000003-1').action_register()

    def test_age_counts_completed_years(self):
        today = fields.Date.today()
        partner = self.Partner.create({'name': 'Birthday', 'date_of_birth': today - relativedelta(years=18) + relativedelta(days=1)})
        self.assertEqual(partner.age, 17)
        partner.date_of_birth = today - relativedelta(years=18)
        self.assertEqual(partner.age, 18)

    def test_mobile_is_never_truncated(self):
        with self.assertRaises(ValidationError):
            self.Partner.create({'name': 'Vendor', 'mobile': '03001234567'})
        self.assertEqual(self.Partner.create({'name': 'Vendor', 'mobile': '3001234567'}).mobile, '3001234567')

    def test_registered_profile_is_locked(self):
        donor = self.Partner.create({'name': 'Locked Donor', 'mobile': '3001000005', 'cnic_no': '42101-1000005-1',
                                     'category_id': [(6, 0, [self.donor.id, self.individual.id])]})
        donor.action_register()
        as_clerk = donor.with_user(self.clerk)
        with self.assertRaises(UserError):
            as_clerk.write({'name': 'Someone Else'})
        with self.assertRaises(UserError):
            as_clerk.write({'category_id': [(3, self.individual.id)]})
        with self.assertRaises(UserError):
            as_clerk.write({'state': 'draft'})
        as_clerk.write({'details': 'Notes stay editable'})
        as_clerk.write({'category_id': [(4, self.employee.id)]})  # adding a tag is allowed
        as_clerk.write({'name': 'Locked Donor'})  # writing an unchanged value is fine
        as_clerk.action_change_request()
        as_clerk.write({'name': 'Corrected Name'})
        as_clerk.action_register()
        self.assertEqual(donor.state, 'register')
        self.assertEqual(donor.name, 'Corrected Name')

    def test_workflow_states(self):
        partner = self._donee('Flow', mobile='3001000006', cnic_no='42101-1000006-1')
        with self.assertRaises(UserError):
            partner.action_change_request()
        partner.action_reject()
        with self.assertRaises(UserError):
            partner.action_register()
        partner.action_reset_to_draft()
        partner.action_register()
        with self.assertRaises(UserError):
            partner.action_reject()
        with self.assertRaises(UserError):
            partner.action_register()

    def test_welfare_without_module_gives_clear_error(self):
        if 'welfare' in self.env:
            self.skipTest('Welfare module installed')
        partner = self._donee('Welfare', mobile='3001000007', cnic_no='42101-1000007-1',
                              category_id=[(6, 0, [self.donee.id, self.individual.id, self.welfare.id])])
        with self.assertRaises(UserError):
            partner.action_register()
        self.assertEqual(partner.state, 'draft')

    def test_search_keeps_existing_tags(self):
        person = self._donee('Multi', mobile='3001000008', cnic_no='42101-1000008-1',
                             category_id=[(6, 0, [self.donee.id, self.donor.id, self.individual.id, self.employee.id])])
        wizard = self.env['confirm.search'].create({'registration_type': 'donee', 'search_type': 'cnic_no',
                                                    'cnic_no': '42101-1000008-1', 'donee_registration_type': 'medical'})
        action = wizard.action_confirm()
        self.assertEqual(action['res_id'], person.id)
        self.assertEqual(set(person.category_id.mapped('name')), {'Donee', 'Donor', 'Individual', 'Employee', 'Medical'})

    def test_search_donor_by_mobile(self):
        donor = self.Partner.create({'name': 'Mobile Donor', 'mobile': '3001000009',
                                     'category_id': [(6, 0, [self.donor.id, self.individual.id])]})
        action = self.env['confirm.search'].create({'registration_type': 'donor', 'search_type': 'mobile_no',
                                                    'mobile_no': '3001000009',
                                                    'country_code_id': self.env.ref('base.pk').id}).action_confirm()
        self.assertEqual(action['res_id'], donor.id)

    def _legacy_duplicate(self, name, cnic):
        """Duplicates can no longer be created; simulate one from before."""
        partner = self._donee(name)
        self.env.cr.execute("UPDATE res_partner SET cnic_no = %s WHERE id = %s", (cnic, partner.id))
        partner.invalidate_recordset(['cnic_no'])
        return partner

    def test_search_several_matches_and_errors(self):
        self._donee('Same 1', cnic_no='42101-1000010-1')
        self._legacy_duplicate('Same 2', '42101-1000010-1')
        action = self.env['confirm.search'].create({'registration_type': 'donee', 'search_type': 'cnic_no',
                                                    'cnic_no': '42101-1000010-1', 'donee_registration_type': 'medical'}).action_confirm()
        self.assertEqual(action['res_model'], 'res.partner')
        self.assertEqual(len(action['domain'][0][2]), 2)
        with self.assertRaises(UserError):
            self.env['confirm.search'].create({'registration_type': 'donee', 'search_type': 'cnic_no',
                                               'cnic_no': '42101-1000010-1'}).action_confirm()
        with self.assertRaises(UserError):
            self.env['confirm.search'].create({'registration_type': 'donor', 'search_type': 'registration_id'}).action_confirm()

    def test_new_profile_from_search_is_prefilled(self):
        action = self.env['confirm.search'].create({'registration_type': 'donee', 'search_type': 'cnic_no',
                                                    'cnic_no': '42101-1000011-1', 'donee_registration_type': 'medical',
                                                    'category': 'institution'}).action_confirm()
        context = action['context']
        self.assertNotIn('res_id', action)
        self.assertEqual(context['default_cnic_no'], '42101-1000011-1')
        self.assertIn(self.medical.id, context['default_category_id'][0][2])

    def test_buttons_through_rpc(self):
        partner = self._donee('RPC', mobile='3001000012', cnic_no='42101-1000012-1')
        model = self.env['res.partner'].with_user(self.clerk)
        call_kw(model, 'action_register', [[partner.id]], {})
        call_kw(model, 'action_change_request', [[partner.id]], {})
        call_kw(model, 'action_bulk_register_donee', [[partner.id]], {})
        self.assertEqual(partner.state, 'register')
        result = call_kw(model, 'web_search_read', [], {'domain': [('id', '=', partner.id)], 'specification': {'state': {}, 'age': {}}})
        self.assertEqual(result['records'][0]['age'], partner.age)


@tagged('post_install', '-at_install')
class TestProfileRegistrationIds(ProfileCase):
    """One contact per person, one ID per tag."""

    def test_donee_and_donor_ids_keep_their_format(self):
        donee = self._donee('Format Donee', mobile='3002000001', cnic_no='42101-2000001-1',
                            date_of_birth=datetime.date(1990, 1, 1), gender='female')
        donee.action_register()
        yy = str(fields.Date.today().year)[2:]
        self.assertRegex(donee.primary_registration_id, r'^%s-90-\d{5}-0$' % yy)
        self.assertEqual(donee.registration_ids.code, donee.primary_registration_id)
        donor = self.Partner.create({'name': 'Format Donor', 'mobile': '3002000002',
                                     'category_id': [(6, 0, [self.donor.id, self.individual.id])]})
        donor.action_register()
        self.assertRegex(donor.primary_registration_id, r'^%s-\d{5}-6$' % yy)

    def test_pattern_configured_on_the_tag(self):
        student = self.env.ref('bn_profile_management.student_partner_category')
        student.write({'registration_pattern': 'STU-{YYYY}-{SEQ}', 'registration_padding': 4})
        self.assertTrue(student.registration_sequence_id)
        self.assertEqual(student.registration_example, 'STU-%s-0012' % fields.Date.today().year)
        person = self._donee('Student P', mobile='3002000003', cnic_no='42101-2000003-1',
                             category_id=[(6, 0, [self.donee.id, self.individual.id, student.id])])
        person.action_register()
        codes = dict((r.category_id.name, r.code) for r in person.registration_ids)
        self.assertEqual(set(codes), {'Donee', 'Student'})
        self.assertRegex(codes['Student'], r'^STU-%s-\d{4}$' % fields.Date.today().year)
        with self.assertRaises(ValidationError):
            student.registration_pattern = 'STU-{YEAR}'

    def test_new_role_on_registered_contact(self):
        person = self.Partner.create({'name': 'Donor First', 'mobile': '3002000004', 'cnic_no': '42101-2000004-1',
                                      'category_id': [(6, 0, [self.donor.id, self.individual.id])],
                                      'date_of_birth': datetime.date(1985, 1, 1), 'gender': 'male'})
        person.action_register()
        donor_id = person.primary_registration_id
        action = self.env['confirm.search'].create({'registration_type': 'donee', 'search_type': 'cnic_no',
                                                    'cnic_no': '42101-2000004-1', 'donee_registration_type': 'medical'}).action_confirm()
        self.assertEqual(action['res_id'], person.id, 'same contact, no duplicate')
        self.assertTrue(person.has_pending_registration)
        self.assertIn('Donee', person.pending_registration_tags)
        person.action_register()
        codes = dict((r.category_id.name, r.code) for r in person.registration_ids)
        self.assertEqual(codes['Donor'], donor_id)
        self.assertIn('Donee', codes)
        self.assertEqual(person.secondary_registration_id, donor_id)
        self.assertFalse(person.has_pending_registration)
        with self.assertRaises(UserError):
            person.action_register()

    def test_one_contact_per_person(self):
        self._donee('Original', mobile='3002000005', cnic_no='42101-2000005-1')
        with self.assertRaisesRegex(ValidationError, 'Original'):
            self.Partner.create({'name': 'Copy by CNIC', 'cnic_no': '42101-2000005-1'})
        with self.assertRaisesRegex(ValidationError, 'Original'):
            self.Partner.create({'name': 'Copy by mobile', 'mobile': '3002000005',
                                 'category_id': [(6, 0, [self.donor.id])]})
        # Sharing a mobile with a non-profile contact (e.g. a vendor) is fine.
        self.Partner.create({'name': 'Vendor same phone', 'mobile': '3002000005'})

    def test_backfill_of_existing_ids(self):
        legacy = self._donee('Legacy', mobile='3002000006', cnic_no='42101-2000006-1')
        self.env.cr.execute("UPDATE res_partner SET state = 'register', primary_registration_id = '24-80-09999-1' WHERE id = %s",
                            (legacy.id,))
        legacy.invalidate_recordset()
        self.env['res.partner.category']._bn_setup_registration_ids()
        self.assertEqual(legacy.registration_ids.code, '24-80-09999-1')
        self.assertEqual(legacy.registration_ids.category_id, self.donee)
        self.env['res.partner.category']._bn_setup_registration_ids()
        self.assertEqual(len(legacy.registration_ids), 1, 'idempotent')

    def test_ids_readable_without_profile_groups(self):
        """An internal user outside Profile Management (cashier, accountant ...)
        can still open contacts and gets the duplicate message, not an access error."""
        person = self._donee('Visible', mobile='3002000007', cnic_no='42101-2000007-1')
        person.action_register()
        outsider = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'profile_outsider',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('base.group_partner_manager').id])]})
        data = person.with_user(outsider).read(['registration_ids', 'has_pending_registration', 'pending_registration_tags'])
        self.assertEqual(len(data[0]['registration_ids']), 1)
        with self.assertRaisesRegex(ValidationError, 'Visible'):
            self.Partner.with_user(outsider).create({'name': 'Copy', 'cnic_no': '42101-2000007-1'})
