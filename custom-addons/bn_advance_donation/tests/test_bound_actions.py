# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestBoundActions(TransactionCase):
    """Action-menu tools that work as superuser are refused to the wrong groups."""

    def test_sync_receipts_managers_only(self):
        user = new_test_user(self.env, 'adv_sync_user', groups='base.group_user,point_of_sale.group_pos_user')
        with self.assertRaises(AccessError):
            self.env['pos.order'].with_user(user).action_sync_advance_donation_receipts()
        action = self.env.ref('bn_advance_donation.action_sync_advance_donation_receipts')
        self.assertEqual(action.groups_id, self.env.ref('bn_advance_donation.group_adv_don_manager'))

    def test_fetch_donor_names_not_for_audit(self):
        if 'import.donation' not in self.env:
            self.skipTest('bn_import_donation not installed')
        audit = new_test_user(self.env, 'imp_audit_user', groups='base.group_user,bn_import_donation.import_donation_audit_group')
        with self.assertRaises(AccessError):
            self.env['import.donation'].with_user(audit).action_fetch_donor_name_from_excel()
