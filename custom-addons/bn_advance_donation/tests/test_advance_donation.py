# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAdvanceDonation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.product = cls.env['product.product'].create({'name': 'Goat T', 'list_price': 1000, 'is_advance_donation': True})
        cls.category = cls.env['advance.donation.category'].create({'name': 'Cat T'})
        cls.donor = cls.env['res.partner'].create({'name': 'Donor T'})

        def user(login, *groups):
            return cls.env['res.users'].create({'name': login, 'login': login, 'groups_id': [
                (6, 0, [ref('base.group_user').id] + [ref(g).id for g in groups])]})
        cls.user = user('ad_t_user', 'bn_advance_donation.group_adv_don_menu')
        cls.approver_1 = user('ad_t_ap1', 'bn_advance_donation.group_adv_don_approval_1')
        cls.approver_2 = user('ad_t_ap2', 'bn_advance_donation.group_adv_don_approval_2')
        cls.treasury = user('ad_t_tre', 'bn_pos_cheque.pos_cheque_menu_group')

    def _donation(self):
        donation = self.env['advance.donation'].with_user(self.user).create({
            'donor_id': self.donor.id, 'category_id': self.category.id, 'contract_type': 'product',
            'product_id': self.product.id, 'amount_percentage': 100, 'total_no_of_product': 2})
        donation.compute_donation()
        return donation

    def test_approval_workflow(self):
        donation = self._donation()
        self.assertEqual(len(donation.advance_donation_lines), 2)
        with self.assertRaises(UserError):
            donation.action_approved()  # still Draft
        donation.action_send_for_approval()
        with self.assertRaises(AccessError):
            donation.action_approved()  # not an approver
        with self.assertRaises(AccessError):
            donation.with_user(self.approver_2).action_approved()  # wrong step
        donation.with_user(self.approver_1).action_approved()
        self.assertEqual(donation.state, 'approval_2')
        with self.assertRaises(UserError):
            donation.with_user(self.approver_2).action_rejected()  # remarks required
        donation.with_user(self.approver_2).action_approved()
        self.assertEqual(donation.state, 'approved')
        self.assertTrue(donation.approved_date)
        with self.assertRaises(UserError):
            donation.compute_donation()

    def test_receipts_and_payment(self):
        Receipt = self.env['advance.donation.receipt'].with_user(self.user)
        cash = Receipt.create({'donor_id': self.donor.id, 'amount': 1500, 'payment_type': 'cash', 'product_id': self.product.id})
        self.assertEqual(cash.date, fields.Date.context_today(cash))
        cash.action_paid()
        with self.assertRaises(UserError):
            cash.action_paid()

        cheque = Receipt.create({'donor_id': self.donor.id, 'amount': 500, 'payment_type': 'cheque', 'product_id': self.product.id})
        with self.assertRaises(UserError):
            cheque.action_paid()  # must be deposited first
        income = self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', self.env.company.id)], limit=1)
        expense = self.env['account.account'].search([('account_type', '=', 'expense'), ('company_id', '=', self.env.company.id)], limit=1)
        self.product.categ_id.write({'property_account_income_categ_id': income.id, 'property_account_expense_categ_id': expense.id})
        moves_before = self.env['account.move'].search_count([('ref', '=', cheque.name)])
        cheque.action_pending()
        self.assertEqual(cheque.state, 'pending')
        self.assertEqual(self.env['account.move'].search_count([('ref', '=', cheque.name)]) - moves_before, 1)
        with self.assertRaises(AccessError):
            cheque.action_paid()  # treasury confirms
        cheque.with_user(self.treasury).action_paid()

        donation = self._donation()
        other = self.env['res.partner'].create({'name': 'Other donor'})
        foreign = self.env['advance.donation.receipt'].create({'donor_id': other.id, 'amount': 100, 'payment_type': 'cash'})
        foreign.action_paid()
        with self.assertRaises(UserError):
            donation.allocate_payment(100, foreign.ids)
        donation.allocate_payment(1500, (cash | cheque).ids)
        self.assertEqual(donation.advance_donation_lines.mapped('state'), ['paid', 'partial'])
        self.assertFalse(donation.is_fully_paid)
