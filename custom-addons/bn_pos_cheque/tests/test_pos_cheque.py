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
        cls.treasury = Users.create({'name': 'Treasury T', 'login': 'chq_t_treasury', 'all_nodes': True, 'groups_id': [
            (6, 0, [ref('base.group_user').id, ref('bn_pos_cheque.pos_cheque_menu_group').id])]})
        cls.cashier = Users.create({'name': 'Cashier T', 'login': 'chq_t_cashier', 'all_nodes': True, 'groups_id': [
            (6, 0, [ref('point_of_sale.group_pos_user').id, ref('bn_pos_cheque.pos_cheque_pos_action_group').id])]})
        cls.user = Users.create({'name': 'User T', 'login': 'chq_t_user', 'all_nodes': True, 'groups_id': [(6, 0, [ref('base.group_user').id])]})

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
        shop = self.env['pos.config'].create({'name': 'CHQ Empty Counter'})
        self.assertEqual(self.env['pos.order'].with_user(self.cashier).get_cheque_pos_order(shop.id)['total_count'], 0)


@tagged('post_install', '-at_install')
class TestPosChequeDetails(TransactionCase):
    """A cheque is created while its order is being made: its donor and amount
    come from the order once linked, the amount being the cheque's part."""

    def test_details_from_order(self):
        env = self.env
        donor = env['res.partner'].create({'name': 'CHQ Details Donor'})
        cash = env['pos.payment.method'].create({'name': 'CHQ Cash', 'is_cash_count': True,
            'journal_id': env['account.journal'].create({'name': 'CHQ Cash', 'code': 'CHQC', 'type': 'cash'}).id})
        cheque_method = env['pos.payment.method'].create({'name': 'CHQ Cheque'})
        config = env['pos.config'].create({'name': 'CHQ Counter', 'payment_method_ids': [(6, 0, (cash | cheque_method).ids)]})
        session = env['pos.session'].create({'config_id': config.id, 'user_id': env.uid})
        cheque = env['pos.cheque'].create({'name': 'CHQ-D1'})
        self.assertEqual(cheque.amount, 0, "no order yet")
        order = env['pos.order'].create({
            'session_id': session.id, 'partner_id': donor.id, 'pos_cheque_id': cheque.id,
            'amount_total': 5000, 'amount_tax': 0, 'amount_paid': 5000, 'amount_return': 0})
        env['pos.payment'].create([
            {'pos_order_id': order.id, 'amount': 1000, 'payment_method_id': cash.id},
            {'pos_order_id': order.id, 'amount': 4000, 'payment_method_id': cheque_method.id}])
        cheque.pos_order_id = order
        self.assertEqual(cheque.donor_id, donor)
        self.assertEqual(cheque.amount, 4000, "the cheque's part of a split payment")
        self.assertTrue(cheque.order_reference)
