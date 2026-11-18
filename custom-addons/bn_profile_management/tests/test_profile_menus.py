from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProfileMenus(TransactionCase):
    """Donor / Donee: the tag drives the installed menu, never a second one."""

    def setUp(self):
        super().setUp()
        self.Tag = self.env['res.partner.category']
        self.donor = self.env.ref('bn_profile_management.donor_partner_category')
        self.menu = self.env.ref('bn_profile_management.donor_profile_management_menu')
        self.action = self.env.ref('bn_profile_management.donor_profile_management_action')
        self.root = self.env.ref('bn_profile_management.profile_management_menu')

    def _donor_menus(self):
        return self.env['ir.ui.menu'].with_context(active_test=False).search(
            [('parent_id', '=', self.root.id), ('name', '=', self.donor.name)])

    def test_installed_menu_is_linked(self):
        self.assertTrue(self.donor.is_profile_type)
        self.assertEqual(self.donor.profile_menu_id, self.menu)
        self.assertEqual(self.donor.profile_action_id, self.action)

    def test_database_installed_before_the_link(self):
        """Older install: tag not linked and not enabled -> linked and enabled on upgrade"""
        self.env.cr.execute("""UPDATE res_partner_category SET is_profile_type = false,
                               profile_menu_id = NULL, profile_action_id = NULL WHERE id = %s""", [self.donor.id])
        self.env.cr.execute("DELETE FROM res_partner_category_form_field_rel WHERE category_id = %s", [self.donor.id])
        self.donor.invalidate_recordset()
        self.Tag._setup_profile_menus()
        self.assertTrue(self.donor.is_profile_type)
        self.assertEqual(self.donor.profile_menu_id, self.menu)
        self.assertTrue(self.menu.active)
        self.assertEqual(self._donor_menus(), self.menu, 'one Donor menu')

    def test_duplicate_menu_is_removed(self):
        """Enabled before the link existed: a second Donor menu was created"""
        self.env.cr.execute("""UPDATE res_partner_category SET is_profile_type = false,
                               profile_menu_id = NULL, profile_action_id = NULL WHERE id = %s""", [self.donor.id])
        self.donor.invalidate_recordset()
        self.donor.is_profile_type = True
        duplicate = self.donor.profile_menu_id
        self.assertNotEqual(duplicate, self.menu)
        self.assertEqual(len(self._donor_menus()), 2)
        self.Tag._setup_profile_menus()
        self.assertFalse(duplicate.exists())
        self.assertEqual(self.donor.profile_menu_id, self.menu)
        self.assertEqual(self._donor_menus(), self.menu)

    def test_disabling_hides_the_installed_menu(self):
        self.donor.is_profile_type = False
        self.assertFalse(self.menu.active)
        self.donor.is_profile_type = True
        self.assertTrue(self.menu.active)
        self.assertEqual(self._donor_menus(), self.menu)


@tagged('post_install', '-at_install')
class TestProgrammeMenus(TransactionCase):
    """A programme's menus in its module follow the tag: disabled -> hidden."""

    def test_disable_hides_and_enable_shows(self):
        Tag = self.env['res.partner.category']
        tag = Tag.create({'name': 'Test Programme', 'registration_program_code': 'test_programme'})
        menu = self.env['ir.ui.menu'].create({'name': 'Test Programme Search'})
        self.env['ir.model.data'].create({'module': 'bn_profile_management', 'name': 'test_programme_menu',
                                          'model': 'ir.ui.menu', 'res_id': menu.id})
        Tag._link_program_menus('test_programme', ['bn_profile_management.test_programme_menu'])
        self.assertEqual(tag.program_menu_ids, menu)
        self.assertTrue(menu.active)
        tag.registration_program_active = False
        self.assertFalse(menu.active, 'disabled: its menu is hidden')
        with self.assertRaises(Exception):
            self.env['record.search'].with_context(default_program_code='test_programme').default_get(['program_id'])
        tag.registration_program_active = True
        self.assertTrue(menu.active)
        Tag._link_program_menus('test_programme', ['bn_profile_management.test_programme_menu'])
        self.assertTrue(menu.active, 'an upgrade keeps it as configured')

    def test_programme_menus_of_installed_modules(self):
        """Every installed programme module links its menus to its tag"""
        Tag = self.env['res.partner.category']
        for code, xmlid in [('welfare', 'bn_welfare.welfare_profile_management_menu'),
                            ('microfinance', 'bn_microfinance.microfinance_profile_management_menu'),
                            ('medical', 'bn_medical_equipment.record_search_medical_menu'),
                            ('sadqa_e_jariya', 'bn_sadqa_e_jariya.sadqa_e_jariya_profile_menu')]:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                self.assertIn(menu, Tag._record_search_program(code).program_menu_ids, code)
