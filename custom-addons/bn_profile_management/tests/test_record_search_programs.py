# -*- coding: utf-8 -*-
import datetime

from lxml import etree

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_profile_management import ProfileCase


@tagged('post_install', '-at_install')
class TestRecordSearchPrograms(ProfileCase):
    """Record Search from configuration: the programmes are tags with a
    code; each one can have its own form layout and required fields; the
    programmes a donee applied to stay on the contact as tags."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.microfinance = cls.env.ref('bn_profile_management.microfinance_partner_category')
        cls.Field = cls.env['ir.model.fields']

    def _fields(self, *names):
        return self.Field.search([('model', '=', 'res.partner'), ('name', 'in', names)])

    def _search(self, cnic, program, **vals):
        wizard = self.env['confirm.search'].create(dict({
            'registration_type': 'donee', 'search_type': 'cnic_no', 'cnic_no': cnic,
            'program_id': program.id}, **vals))
        return wizard, wizard.action_confirm()

    # ------------------------------------------------------------------
    def test_programmes_configured(self):
        Tag = self.env['res.partner.category']
        self.assertEqual(Tag._record_search_program('welfare'), self.welfare)
        self.assertEqual(Tag._record_search_program('medical'), self.medical)
        self.assertEqual(self.microfinance.registration_kind, 'individual')
        self.assertFalse(Tag._record_search_program('unknown'))

    def test_module_menu_presets_the_programme(self):
        wizard = self.env['record.search'].with_context(
            default_program_code='microfinance', default_program_locked=True).create({'search_type': 'cnic_no'})
        self.assertEqual(wizard.program_id, self.microfinance)
        self.assertTrue(wizard.program_locked)
        self.assertEqual((wizard.registration_type, wizard.category), ('donee', 'individual'))
        # menus of other modules still passing the older keys
        legacy = self.env['record.search'].with_context(
            default_donee_registration_type='medical', default_is_medical=True).create({'search_type': 'cnic_no'})
        self.assertEqual(legacy.program_id, self.medical)
        self.assertTrue(legacy.program_locked)

    def test_new_programme_without_code_change(self):
        """A new module only adds a tag with a code."""
        housing = self.env['res.partner.category'].create({
            'name': 'Housing', 'registration_program_code': 'housing', 'registration_role': 'donee'})
        wizard = self.env['record.search'].with_context(default_program_code='housing').create({'search_type': 'cnic_no'})
        self.assertEqual(wizard.program_id, housing)
        _wizard, action = self._search('42101-3000001-1', housing)
        self.assertIn(housing.id, action['context']['default_category_id'][0][2])

    def test_form_layout_of_the_programme(self):
        _wizard, action = self._search('42101-3000002-1', self.welfare)
        self.assertEqual(action['context']['profile_tag_view_ref'], self.donee.id,
                         'a programme without its own layout opens with the role layout')
        self.welfare.write({'is_profile_type': True,
                            'profile_form_field_ids': [(6, 0, self._fields('father_name', 'religion').ids)]})
        _wizard, action = self._search('42101-3000003-1', self.welfare)
        self.assertEqual(action['context']['profile_tag_view_ref'], self.welfare.id)
        self.assertTrue(action['context']['from_record_search'])

    def test_required_fields_of_the_programme(self):
        self.medical.registration_required_field_ids = self._fields('father_name', 'cnic_no')
        partner = self._donee('Needs Father', mobile='3001300001', cnic_no='42101-3000004-1',
                              category_id=[(6, 0, (self.donee | self.individual | self.medical).ids)])
        self.assertIn(',father_name,', partner.profile_required_field_names)
        # shown and required on the form until registered
        Partner = self.env['res.partner'].with_context(profile_tag_view_ref=self.donee.id)
        arch = etree.fromstring(Partner.get_views(
            [(self.env.ref('bn_profile_management.profile_management_view_form').id, 'form')])['views']['form']['arch'])
        node = arch.xpath('//field[@name="father_name"]')[0]
        self.assertIn("',father_name,' in (profile_required_field_names or '')", node.get('required'))
        self.assertIn("',father_name,' not in (profile_required_field_names or '')", node.get('invisible'))
        # and checked when registering
        with self.assertRaises(ValidationError) as error:
            partner.action_register()
        self.assertIn('Medical', str(error.exception))
        self.assertEqual(partner.state, 'draft')
        partner.father_name = 'Aslam'
        partner.action_register()
        self.assertEqual(partner.state, 'register')

    def test_required_field_hidden_by_the_form_is_not_asked(self):
        """The CNIC is not asked of someone without one (the form hides it)."""
        self.medical.registration_required_field_ids = self._fields('cnic_no')
        partner = self._donee('No CNIC', mobile='3001300002', has_cnic='no',
                              category_id=[(6, 0, (self.donee | self.individual | self.medical).ids)])
        self.assertFalse(partner._program_missing_fields())

    def test_programmes_tracked_on_the_contact(self):
        partner = self._donee('Many Programmes', mobile='3001300003', cnic_no='42101-3000005-1',
                              date_of_birth=datetime.date(1985, 1, 1))
        self.assertEqual(partner.registered_program_count, 0)
        self._search('42101-3000005-1', self.medical)
        self._search('42101-3000005-1', self.welfare)
        self._search('42101-3000005-1', self.medical)   # same programme again: no duplicate tag
        self.assertEqual(partner.registered_program_ids, self.medical | self.welfare)
        self.assertEqual(partner.registered_program_count, 2)
        several = self.Partner.search([('registered_program_count', '>', 1), ('id', '=', partner.id)])
        self.assertEqual(several, partner)
