# -*- coding: utf-8 -*-
from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

G = 'bn_livestock_slaugther.livestock_slaugther_%s_group'


@tagged('post_install', '-at_install')
class TestLivestockAccess(TransactionCase):
    """Livestock follows the access structure of every module: Menu, User,
    Manager, Audit, Administrator and the Welfare Approval role."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def user(login, *tiers):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [cls.env.ref('base.group_user').id] + [cls.env.ref(G % t).id for t in tiers])]})
        cls.user = user('ls_user', 'menu', 'user')
        cls.manager = user('ls_manager', 'menu', 'manager')
        cls.auditor = user('ls_audit', 'menu', 'audit')
        cls.admin = user('ls_admin', 'menu', 'admin')
        cls.welfare = user('ls_welfare', 'menu', 'welfare_approval')
        cls.employee = user('ls_none')

    def test_tiers(self):
        admin_groups = self.admin.groups_id
        for tier in ('user', 'manager', 'audit'):
            self.assertIn(self.env.ref(G % tier), admin_groups)
        self.assertIn(self.env.ref(G % 'user'), self.manager.groups_id)
        self.assertIn(self.env.ref(G % 'user'), self.welfare.groups_id, 'the role carries User')
        self.assertNotIn(self.env.ref(G % 'menu'), self.env.ref(G % 'admin').implied_ids, 'Menu is given explicitly')

    def test_document_access(self):
        center = self.env['distribution.center'].with_user(self.user).create({})
        center.with_user(self.user).write({'state': 'draft'})
        self.assertTrue(center.with_user(self.auditor).read(['state']))
        with self.assertRaises(AccessError):
            center.with_user(self.auditor).write({'state': 'draft'})
        with self.assertRaises(AccessError):
            center.with_user(self.user).unlink()
        with self.assertRaises(AccessError):
            self.env['livestock.slaugther'].with_user(self.employee).search([])
        center.with_user(self.admin).unlink()

    def test_manager_and_role_steps(self):
        center = self.env['distribution.center'].create({})
        for method in ('action_issue_purchase_requisition', 'action_issue_delivery_note', 'action_welfare_approve'):
            with self.assertRaises(UserError, msg=method):
                getattr(center.with_user(self.user), method)()
        center.with_user(self.welfare).action_welfare_approve()
        self.assertEqual(center.state, 'welfare_approved')

    def test_menus_and_buttons(self):
        Menu = self.env['ir.ui.menu']
        root = self.env.ref('bn_livestock_slaugther.livestock_menu')
        self.assertTrue(Menu.with_user(self.user).search([('id', '=', root.id)]))
        self.assertFalse(Menu.with_user(self.employee).search([('id', '=', root.id)]))
        config = self.env.ref('bn_livestock_slaugther.custom_product_packaging_menu')
        self.assertFalse(Menu.with_user(self.manager).search([('id', '=', config.id)]))
        form = self.env.ref('bn_livestock_slaugther.distribution_center_view_form')
        for user, shown in ((self.manager, True), (self.user, False)):
            arch = etree.fromstring(self.env['distribution.center'].with_user(user).get_views(
                [(form.id, 'form')])['views']['form']['arch'])
            self.assertEqual(bool(arch.xpath('//button[@name="action_issue_purchase_requisition"]')), shown, user.login)
