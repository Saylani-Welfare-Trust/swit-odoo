# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestTreasuryGate(TransactionCase):
    """A Purchase Order bill is paid only once Finance confirmed it (forwarded to
    Treasury); other vendor bills are not held."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'Gate Vendor'})
        cls.product = cls.env['product.product'].create({'name': 'Gate Product', 'detailed_type': 'consu',
                                                          'standard_price': 100})
        cls.order = cls.env['purchase.order'].create({
            'partner_id': cls.vendor.id,
            'order_line': [(0, 0, {'product_id': cls.product.id, 'product_qty': 2, 'price_unit': 100})],
        })
        cls.accountant = new_test_user(cls.env, 'gate_accountant',
                                       groups='base.group_user,account.group_account_manager')
        cls.finance = new_test_user(cls.env, 'gate_finance',
                                    groups='base.group_user,account.group_account_manager,'
                                           'bn_procurement_finance.group_finance')

    def _bill(self, purchase=True):
        line = {'product_id': self.product.id, 'quantity': 2, 'price_unit': 100, 'tax_ids': [(6, 0, [])]}
        if purchase:
            line['purchase_line_id'] = self.order.order_line.id
        return self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.vendor.id,
            'invoice_date': '2026-11-01', 'invoice_line_ids': [(0, 0, line)],
        })

    def _pay(self, bill, user):
        wizard = self.env['account.payment.register'].with_user(user).with_context(
            active_model='account.move', active_ids=bill.ids).create({})
        return wizard._create_payments()

    def test_po_bill_posted_without_finance_is_held(self):
        bill = self._bill()
        bill.action_post()
        self.assertFalse(bill.forwarded_to_treasury)
        with self.assertRaises(UserError):
            self._pay(bill, self.accountant)
        # Finance confirms the posted bill: forwarded, then it can be paid
        bill.with_user(self.finance).action_finance_confirm_and_post()
        self.assertTrue(bill.finance_confirmed and bill.forwarded_to_treasury)
        self.assertEqual(bill.treasury_forwarded_by, self.finance)
        self._pay(bill, self.accountant)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))

    def test_finance_confirm_and_post_from_draft(self):
        bill = self._bill()
        bill.with_user(self.finance).action_finance_confirm_and_post()
        self.assertEqual(bill.state, 'posted')
        self.assertTrue(bill.forwarded_to_treasury)
        with self.assertRaises(UserError):
            bill.with_user(self.finance).action_finance_confirm_and_post()

    def test_assigned_treasury_officer(self):
        bill = self._bill()
        bill.treasury_user_id = self.finance
        bill.with_user(self.finance).action_finance_confirm_and_post()
        with self.assertRaises(UserError):
            self._pay(bill, self.accountant)
        self._pay(bill, self.finance)

    def test_other_vendor_bills_not_held(self):
        bill = self._bill(purchase=False)
        bill.action_post()
        self._pay(bill, self.accountant)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
