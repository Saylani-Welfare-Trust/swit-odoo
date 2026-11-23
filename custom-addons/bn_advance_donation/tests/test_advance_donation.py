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
        # deposit entries and refunds go to the configured Advance Donation Journal
        cls.env.company.advance_donation_journal_id = cls.env['account.journal'].create(
            {'name': 'AD Test Bank', 'code': 'ADTB', 'type': 'bank', 'company_id': cls.env.company.id})

        Users = cls.env['res.users']
        # products are limited to the user's categories when that rule is installed
        categories = ({'allowed_product_category_ids': [(6, 0, cls.product.categ_id.ids)]}
                      if 'allowed_product_category_ids' in Users._fields else {})

        def user(login, *groups):
            return Users.create(dict(categories, name=login, login=login, groups_id=[
                (6, 0, [ref('base.group_user').id] + [ref(g).id for g in groups])]))
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

    def _approve(self, donation):
        donation.action_send_for_approval()
        donation.with_user(self.approver_1).action_approved()
        donation.with_user(self.approver_2).action_approved()
        self.assertEqual(donation.state, 'approved')

    def _paid_receipt(self, amount):
        receipt = self.env['advance.donation.receipt'].create(
            {'donor_id': self.donor.id, 'amount': amount, 'payment_type': 'cash'})
        receipt.action_paid()
        return receipt

    def test_slip_and_disbursement_only_when_approved(self):
        donation = self._donation()
        receipt = self._paid_receipt(1000)
        line = donation.advance_donation_lines[0]
        for step in ('draft', 'approval_1', 'approval_2'):
            if step == 'approval_1':
                donation.action_send_for_approval()
            elif step == 'approval_2':
                donation.with_user(self.approver_1).action_approved()
            self.assertEqual(donation.state, step)
            with self.assertRaises(UserError):
                donation.allocate_payment(500, receipt.ids)
            with self.assertRaises(UserError):
                donation.action_open_payment_wizard()
            with self.assertRaises(UserError):
                donation.write({'donation_slip_ids': [(4, receipt.id)]})
            with self.assertRaises(UserError):
                line.write({'is_disbursed': True})
        self.assertFalse(donation.donation_slip_ids)
        self.assertFalse(line.is_disbursed)

        donation.with_user(self.approver_2).action_approved()
        self.assertEqual(donation.state, 'approved')
        donation.action_open_payment_wizard()
        donation.allocate_payment(500, receipt.ids)
        self.assertEqual(donation.donation_slip_ids, receipt)
        line.write({'is_disbursed': True})
        self.assertTrue(line.is_disbursed)
        self.assertTrue(line.disbursement_date)

    def test_open_contract_has_no_frequency_or_dates(self):
        empty = {'contract_frequency': False, 'contract_start_date': False,
                 'contract_end_date': False, 'no_of_days': 0, 'no_of_weeks': 0}
        values = lambda d: {f: d[f] for f in empty}
        dated = {'contract_frequency': 'daily', 'contract_start_date': '2026-01-01',
                 'contract_end_date': '2026-01-10'}

        # switching to Open Contract in the form empties them
        new = self.env['advance.donation'].new(dict(dated, contract_type='frequency'))
        new.contract_type = 'open_contract'
        new._onchange_contract_type()
        self.assertEqual(values(new), empty)
        new.contract_type = 'frequency'
        new._onchange_contract_type()
        self.assertEqual(new.contract_frequency, 'daily')

        # and they are never stored, whatever is sent
        donation = self.env['advance.donation'].with_user(self.user).create(dict(
            dated, donor_id=self.donor.id, category_id=self.category.id, product_id=self.product.id,
            contract_type='open_contract', total_product_amount=900))
        self.assertEqual(values(donation), empty)
        donation.write({'contract_type': 'frequency', **dated})
        self.assertEqual(donation.contract_frequency, 'daily')
        donation.write({'contract_type': 'open_contract'})
        self.assertEqual(values(donation), empty)

        # one line for the whole amount
        donation.compute_donation()
        self.assertEqual(len(donation.advance_donation_lines), 1)
        self.assertEqual(donation.advance_donation_lines.amount, 900)

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
            donation.allocate_payment(1500, (cash | cheque).ids)  # not approved yet
        self._approve(donation)
        with self.assertRaises(UserError):
            donation.allocate_payment(100, foreign.ids)
        donation.allocate_payment(1500, (cash | cheque).ids)
        self.assertEqual(donation.advance_donation_lines.mapped('state'), ['paid', 'partial'])
        self.assertFalse(donation.is_fully_paid)

    def test_terms_fixed_once_sent_for_approval(self):
        """What the approvers approve is what is paid: the terms and the lines
        can only be changed (or lines deleted) in Draft."""
        donation = self._donation()
        line = donation.advance_donation_lines[:1]
        donation.write({'amount_percentage': 50})  # Draft: free
        donation.compute_donation()
        line = donation.advance_donation_lines[:1]
        line.write({'comment': 'draft'})
        self._approve(donation)
        with self.assertRaises(UserError):
            donation.write({'amount_percentage': 100})
        with self.assertRaises(UserError):
            donation.write({'donor_id': self.env['res.partner'].create({'name': 'Other T'}).id})
        with self.assertRaises(UserError):
            line.write({'amount': line.amount + 1})
        with self.assertRaises(UserError):
            line.unlink()
        # an unchanged value, a comment or the payment fields stay writable
        donation.write({'amount_percentage': donation.amount_percentage})
        line.write({'comment': 'approved', 'paid_amount': line.paid_amount})

    def test_cancel_payment_keeps_partly_disbursed_lines(self):
        """Cancel Payment refunds only lines nothing was disbursed from."""
        donation = self._donation()
        self._approve(donation)
        receipt = self._paid_receipt(sum(donation.advance_donation_lines.mapped('remaining_amount')))
        donation.allocate_payment(receipt.amount, receipt.ids)
        partly, untouched = donation.advance_donation_lines[0], donation.advance_donation_lines[1]
        paid = partly.paid_amount
        partly.write({'disbursed_amount': paid / 2})  # half used, line not fully disbursed
        donation.action_cancel_payment()
        self.assertEqual(partly.paid_amount, paid, 'the used line keeps its payment')
        self.assertEqual(untouched.paid_amount, 0.0)
