# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.bn_profile_management.models.res_partner_category import (
    LEGACY_LIST_FIELDS, LEGACY_SEARCH_FIELDS)


@tagged('post_install', '-at_install')
class TestDynamicProfileViews(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Field = cls.env['ir.model.fields']
        cls.student = cls.env.ref('bn_profile_management.student_partner_category')
        cls.student.write({
            'is_profile_type': True,
            'profile_list_field_ids': [(6, 0, cls._ids(['religion', 'phone', 'image_1920']))],
            'profile_search_field_ids': [(6, 0, cls._ids(['religion', 'phone', 'image_1920', 'age']))],
            'profile_form_field_ids': [(6, 0, cls._ids(['phone', 'religion']))],
        })

    @classmethod
    def _ids(cls, names):
        return cls.env['ir.model.fields'].search([('model', '=', 'res.partner'), ('name', 'in', names)]).ids

    def _arch(self, view_type, tag):
        Partner = self.env['res.partner'].with_context(profile_tag_view_ref=tag.id)
        views = Partner.get_views([(self.env.ref('bn_profile_management.profile_management_view_%s' % view_type).id, view_type)])
        return etree.fromstring(views['views'][view_type]['arch'])

    def _fields(self, arch, tag_name):
        return [n.get('name') for n in arch.iter(tag_name) if n.get('name')]

    def test_menu_passes_its_tag(self):
        self.assertEqual(eval(self.student.profile_action_id.context)['profile_tag_view_ref'], self.student.id)
        donor = self.env.ref('bn_profile_management.donor_partner_category')
        self.assertIn("'profile_tag_view_ref': %s" % donor.id, donor.profile_action_id.context)
        self.assertNotIn('profile_category_id', donor.profile_action_id.context)

    def test_list_columns_follow_the_tag(self):
        columns = self._fields(self._arch('tree', self.student), 'field')
        self.assertIn('religion', columns)
        self.assertIn('phone', columns)
        self.assertIn('image_1920', columns)
        self.assertNotIn('cnic_no', columns)
        self.assertLess(columns.index('religion'), columns.index('state'))

    def test_search_fields_follow_the_tag(self):
        fields = self._fields(self._arch('search', self.student), 'field')
        self.assertIn('religion', fields)
        self.assertIn('phone', fields)
        self.assertNotIn('image_1920', fields, 'images cannot be searched')
        self.assertNotIn('age', fields, 'computed, not searchable')
        self.assertNotIn('cnic_no', fields)

    def test_changing_the_tag_rebuilds_the_views(self):
        self.assertNotIn('vat', self._fields(self._arch('tree', self.student), 'field'))
        self.student.profile_list_field_ids = [(4, self._ids(['vat'])[0])]
        self.assertIn('vat', self._fields(self._arch('tree', self.student), 'field'))

    def test_form_shows_fields_selected_by_the_contacts_tags(self):
        arch = self._arch('form', self.student)
        phone = arch.xpath('//sheet//field[@name="phone"]')
        self.assertTrue(phone, 'phone had no slot on the form before')
        self.assertIn("',phone,' not in profile_visible_form_field_names", phone[0].get('invisible'))
        email = arch.xpath('//sheet//field[@name="email"]')[0]
        self.assertIn("',email,' not in profile_visible_form_field_names", email.get('invisible'))
        self.assertFalse(arch.xpath('//sheet//field[@name="name"]')[0].get('invisible'), 'name always visible')
        contact = self.env['res.partner'].create({'name': 'Student C', 'category_id': [(6, 0, self.student.ids)]})
        self.assertIn(',phone,', contact.profile_visible_form_field_names)
        self.assertNotIn(',email,', contact.profile_visible_form_field_names)

    def test_donor_and_donee_keep_their_previous_columns(self):
        for xmlid in ('donor_partner_category', 'donee_partner_category'):
            tag = self.env.ref('bn_profile_management.' + xmlid)
            self.assertEqual(set(tag.profile_list_field_ids.mapped('name')), set(LEGACY_LIST_FIELDS))
            self.assertEqual(set(tag.profile_search_field_ids.mapped('name')), set(LEGACY_SEARCH_FIELDS))
            columns = self._fields(self._arch('tree', tag), 'field')
            self.assertEqual(set(columns) - {'complete_name', 'state'}, set(LEGACY_LIST_FIELDS))

    def test_views_without_a_tag_unchanged(self):
        arch = etree.fromstring(self.env['res.partner'].get_views(
            [(self.env.ref('bn_profile_management.profile_management_view_tree').id, 'tree')])['views']['tree']['arch'])
        self.assertTrue(arch.xpath('//field[@column_invisible]'), 'legacy context flags still work')

    def test_configuration_under_master_setup(self):
        config = self.env.ref('bn_profile_management.profile_management_config_menu')
        self.assertEqual(config.parent_id, self.env.ref('bn_master_setup.master_setup_menu'))
        manager = self.env['res.users'].create({
            'name': 'Profile Manager Only', 'login': 'pm_manager_only',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('bn_profile_management.profile_management_manager_group').id])]})
        visible = self.env['ir.ui.menu'].with_user(manager)._visible_menu_ids()
        for xmlid in ('bn_master_setup.master_setup_menu', 'bn_profile_management.profile_management_config_menu',
                      'bn_profile_management.res_partner_category_menu_profile', 'bn_profile_management.area_menu'):
            self.assertIn(self.env.ref(xmlid).id, visible, xmlid)

    def _set_order(self, view_type, names):
        lines = self.student._profile_view_lines(view_type)
        for position, name in enumerate(names):
            lines.filtered(lambda l: l.field_id.name == name).sequence = position

    def test_list_columns_in_chosen_order(self):
        self._set_order('list', ['image_1920', 'phone', 'religion'])
        columns = [c for c in self._fields(self._arch('tree', self.student), 'field') if c not in ('complete_name', 'state')]
        self.assertEqual(columns, ['image_1920', 'phone', 'religion'])
        self._set_order('list', ['religion', 'image_1920', 'phone'])
        columns = [c for c in self._fields(self._arch('tree', self.student), 'field') if c not in ('complete_name', 'state')]
        self.assertEqual(columns, ['religion', 'image_1920', 'phone'])

    def test_search_fields_in_chosen_order(self):
        self._set_order('search', ['religion', 'phone'])
        fields = self._fields(self._arch('search', self.student), 'field')
        self.assertLess(fields.index('religion'), fields.index('phone'))
        self._set_order('search', ['phone', 'religion'])
        fields = self._fields(self._arch('search', self.student), 'field')
        self.assertLess(fields.index('phone'), fields.index('religion'))

    def test_form_fields_in_chosen_order(self):
        self.student.profile_form_field_ids = [(6, 0, self._ids(['religion', 'phone', 'gender', 'cnic_no']))]
        self._set_order('form', ['cnic_no', 'religion', 'phone', 'gender'])
        page = self._arch('form', self.student).xpath('//page[@name="general_info"]')[0]
        left = [n.get('name') for n in page.xpath('.//group[@name="general_info_col_1"]/field')]
        right = [n.get('name') for n in page.xpath('.//group[@name="general_info_col_2"]/field')]
        self.assertEqual(left, ['cnic_no', 'religion'])
        self.assertEqual(right[:2], ['phone', 'gender'])
        cnic = page.xpath('.//field[@name="cnic_no"]')[0]
        self.assertIn("has_cnic == 'no'", cnic.get('invisible'), 'the field keeps its own rules')

    def test_selection_and_lines_stay_in_sync(self):
        self.student.profile_list_field_ids = [(4, self._ids(['vat'])[0])]
        lines = self.student._profile_view_lines('list')
        self.assertEqual(lines[-1].field_id.name, 'vat', 'new field added at the end')
        lines.filtered(lambda l: l.field_id.name == 'phone').unlink()
        self.assertNotIn('phone', self.student.profile_list_field_ids.mapped('name'))

    def test_order_from_the_tag_form(self):
        from odoo.tests import Form
        with Form(self.student, view='bn_profile_management.res_partner_category_view_form_profile') as form:
            with form.profile_list_line_ids.new() as line:
                line.field_id = self.env['ir.model.fields'].browse(self._ids(['website']))
        self.assertIn('website', self.student.profile_list_field_ids.mapped('name'))
        self.assertIn('website', self._fields(self._arch('tree', self.student), 'field'))
