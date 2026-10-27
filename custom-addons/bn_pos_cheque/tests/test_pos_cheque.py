# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosCheque(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.bank = cls.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        Users = cls.env['res.users']
        cls.treasury = Users.create({'name': 'Treasury T', 'login': 'chq_t_treasury', 'groups_id': [
            (6, 0, [ref('base.group_user').id, ref('bn_pos_cheque.pos_cheque_menu_group').id])]})
        cls.cashier = Users.create({'name': 'Cashier T', 'login': 'chq_t_cashier', 'groups_id': [
            (6, 0, [ref('point_of_sale.group_pos_user').id, ref('bn_pos_cheque.pos_cheque_pos_action_group').id])]})
        cls.user = Users.create({'name': 'User T', 'login': 'chq_t_user', 'groups_id': [(6, 0, [ref('base.group_user').id])]})

    def _cheque(self, name):
        return self.env['pos.cheque'].create({'name': name, 'bank_id': self.bank.id})

    def test_lifecycle(self):
        cheque = self._cheque('CHQ-L1').with_user(self.treasury)
        cheque.action_bounce()
        self.assertEqual((cheque.state, cheque.bounce_count), ('bounce', 1))
        with self.assertRaises(UserError):
            cheque.action_bounce()  # must be re-deposited first
        cheque.action_redeposit()
        cheque.action_clear()
        self.assertEqual(cheque.state, 'clear')
        for action in (cheque.action_clear, cheque.action_bounce, cheque.action_redeposit, cheque.action_cancel):
            with self.assertRaises(UserError):
                action()

    def test_bounce_limit_then_settle(self):
        cheque = self._cheque('CHQ-L2').with_user(self.treasury)
        for _i in range(3):
            cheque.action_bounce()
            cheque.action_redeposit()
        cheque.action_bounce()
        self.assertEqual(cheque.bounce_count, 4)
        with self.assertRaises(UserError):
            cheque.action_redeposit()
        with self.assertRaises(UserError):
            cheque.action_clear()
        cheque.action_cancel()
        self.assertEqual(cheque.state, 'cancel')

    def test_access(self):
        cheque = self._cheque('CHQ-L3')
        with self.assertRaises(AccessError):
            cheque.with_user(self.cashier).action_clear()
        with self.assertRaises(AccessError):
            cheque.with_user(self.user).write({'bounce_count': 0})
        with self.assertRaises(AccessError):
            self.env['pos.order'].with_user(self.user).get_cheque_pos_order(1)
        self.assertEqual(self.env['pos.order'].with_user(self.cashier).get_cheque_pos_order(1)['total_count'], 0)
