# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged



def _with_stock_scope(user):
    """Like a configured user (bn_stock_location scope): every warehouse,
    internal location and product category of the test database."""
    if 'allowed_warehouse_ids' in user._fields:
        env = user.env
        user.write({
            'allowed_warehouse_ids': [(6, 0, env['stock.warehouse'].search([]).ids)],
            'allowed_location_ids': [(6, 0, env['stock.location'].search([('usage', '=', 'internal')]).ids)],
            'allowed_product_category_ids': [(6, 0, env['product.category'].search([]).ids)],
        })
    return user

@tagged('post_install', '-at_install')
class TestMicrofinance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        ref = env.ref
        company = env.company
        Account = env['account.account']
        expense = Account.search([('account_type', '=', 'expense'), ('company_id', '=', company.id)], limit=1)
        Product = env['product.product']
        cls.cash_product = Product.create({'name': 'Cash Loan T', 'type': 'service', 'list_price': 50000,
                                           'is_microfinance': True, 'property_account_expense_id': expense.id})
        cls.bike = Product.create({'name': 'Bike T', 'type': 'product', 'list_price': 120000, 'is_microfinance': True})
        cls.warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        env['stock.quant']._update_available_quantity(cls.bike, cls.warehouse.lot_stock_id, 2)
        cls.scheme = env['microfinance.scheme'].create({'name': 'Scheme T', 'prefix': 'ST/', 'installment_type': 'monthly'})
        SchemeLine = env['microfinance.scheme.line']
        cls.cash_line = SchemeLine.create({'microfinance_scheme_id': cls.scheme.id, 'name': 'Cash', 'asset_type': 'cash'})
        cls.bike_line = SchemeLine.create({'microfinance_scheme_id': cls.scheme.id, 'name': 'Bike', 'asset_type': 'movable_asset'})
        ProductLine = env['loan.product.line']
        cls.cash_product_line = ProductLine.create({
            'microfinance_scheme_line_id': cls.cash_line.id, 'product_id': cls.cash_product.id, 'sd_amount': 5000,
            'inst_amount': 3750, 'installment_ids': [(0, 0, {'no_of_installment': 12})]})
        cls.bike_product_line = ProductLine.create({
            'microfinance_scheme_line_id': cls.bike_line.id, 'product_id': cls.bike.id, 'sd_amount': 20000,
            'inst_amount': 10000, 'installment_ids': [(0, 0, {'no_of_installment': 10})]})
        tags = [ref('bn_profile_management.donee_partner_category').id,
                ref('bn_profile_management.individual_partner_category').id,
                ref('bn_profile_management.microfinance_partner_category').id]
        cls.donee = env['res.partner'].create({'name': 'Loan Taker T', 'mobile': '3029876543', 'date_of_birth': '1990-01-01',
                                               'category_id': [(6, 0, tags)]})

        def user(login, *groups):
            return _with_stock_scope(env['res.users'].create({'name': login, 'login': login, 'groups_id': [
                (6, 0, [ref('base.group_user').id] + [ref(g).id for g in groups])]}))
        group = 'bn_microfinance.microfinance_%s_group'
        cls.user = user('mf_t_user', group % 'user')
        cls.hod = user('mf_t_hod', group % 'hod')
        cls.member = user('mf_t_member', group % 'member')
        cls.recovery = user('mf_t_recovery', group % 'recovery')
        cls.write_off_1 = user('mf_t_wo1', 'bn_microfinance.microfinance_write_off_approval_1_group')
        cls.write_off_2 = user('mf_t_wo2', 'bn_microfinance.microfinance_write_off_approval_2_group')
        cls.cashier = user('mf_t_pos', group % 'pos_action')
        cls.auditor = user('mf_t_audit', group % 'audit')
        cls.storekeeper = user('mf_t_stock', 'stock.group_stock_user')
        cls.accountant = user('mf_t_acc', 'account.group_account_invoice')

    def _loan(self, scheme_line, product_line):
        loan = self.env['microfinance'].with_user(self.user).create({
            'donee_id': self.donee.id, 'microfinance_scheme_id': self.scheme.id,
            'microfinance_scheme_line_id': scheme_line.id, 'product_id': product_line.product_id.id})
        loan.no_of_installment_id = product_line.installment_ids
        loan.action_move_to_hod()
        loan.with_user(self.hod).action_move_to_member()
        loan.with_user(self.member).action_approve()
        loan.action_sd_slip()
        Installment = self.env['microfinance.installment'].with_user(self.cashier)
        result = Installment.create_microfinance_security_deposit(
            {'microfinance_request_no': loan.name, 'amount': loan.security_deposit})
        self.assertEqual(result['status'], 'success')
        loan.write({'sd_slip_id': result['deposit_id'], 'delivery_date': fields.Date.today()})
        return loan

    def _set_overdue(self, line, days):
        """Move the due date of an installment the given number of days before today."""
        line.sudo().due_date = fields.Date.today() - timedelta(days=days)

    def test_send_for_recovery_needs_installment_unpaid_over_60_days(self):
        loan = self._loan(self.cash_line, self.cash_product_line)
        loan.action_move_to_treasury()
        loan.sudo()._complete_application()
        self.assertEqual(loan.state, 'done')
        self.assertFalse(loan.can_send_to_recovery)
        with self.assertRaises(UserError):
            loan.action_send_to_recovery()

        last, before_last = loan.microfinance_line_ids[-1], loan.microfinance_line_ids[-2]
        self._set_overdue(last, 60)
        self.assertFalse(loan.can_send_to_recovery, 'exactly 60 days overdue is not enough')
        self._set_overdue(last, 61)
        self.assertTrue(loan.can_send_to_recovery)

        last.sudo().write({'paid_amount': last.amount, 'state': 'paid'})
        self.assertFalse(loan.can_send_to_recovery, 'a paid installment does not count')

        self._set_overdue(before_last, 61)
        self.assertTrue(loan.can_send_to_recovery)
        loan.action_send_to_recovery()
        self.assertEqual(loan.state, 'in_recovery')

    def test_send_several_loans_for_recovery(self):
        loans = self.env['microfinance']
        for _i in range(2):
            loan = self._loan(self.cash_line, self.cash_product_line)
            loan.action_move_to_treasury()
            loan.sudo()._complete_application()
            loans |= loan
        overdue, recent = loans
        self._set_overdue(overdue.microfinance_line_ids[-1], 61)
        self._set_overdue(recent.microfinance_line_ids[-1], 20)

        # one loan not overdue long enough: none is sent, and the error names it
        with self.assertRaises(ValidationError) as error:
            loans.action_send_to_recovery()
        self.assertIn('%s - 20 day(s) overdue' % recent.name, str(error.exception))
        self.assertNotIn('%s - ' % overdue.name, str(error.exception))
        self.assertEqual(loans.mapped('state'), ['done', 'done'])

        self._set_overdue(recent.microfinance_line_ids[-1], 61)
        loans.action_send_to_recovery()
        self.assertEqual(loans.mapped('state'), ['in_recovery', 'in_recovery'])
        self.assertTrue(all(loans.mapped('in_recovery')))
        self.assertEqual(len(overdue.microfinance_recovery_line_ids), len(overdue.microfinance_line_ids))

    def test_approval_roles(self):
        loan = self.env['microfinance'].with_user(self.user).create({
            'donee_id': self.donee.id, 'microfinance_scheme_id': self.scheme.id,
            'microfinance_scheme_line_id': self.cash_line.id, 'product_id': self.cash_product.id})
        loan.no_of_installment_id = self.cash_product_line.installment_ids
        with self.assertRaises(AccessError):
            loan.action_approve()
        with self.assertRaises(UserError):
            loan.write({'state': 'approve'})
        loan.action_move_to_hod()
        with self.assertRaises(AccessError):
            loan.action_move_to_member()
        loan.with_user(self.hod).action_move_to_member()
        loan.sudo().mem_remarks = 'check again'
        with self.assertRaises(AccessError):
            loan.with_user(self.hod).action_revert()
        loan.with_user(self.member).action_revert()
        self.assertEqual(loan.state, 'hod_approve')

    def test_cash_loan(self):
        loan = self.env['microfinance'].with_user(self.user).create({
            'donee_id': self.donee.id, 'microfinance_scheme_id': self.scheme.id,
            'microfinance_scheme_line_id': self.cash_line.id, 'product_id': self.cash_product.id})
        loan.no_of_installment_id = self.cash_product_line.installment_ids
        loan.action_move_to_hod()
        loan.with_user(self.hod).action_move_to_member()
        loan.with_user(self.member).action_approve()
        loan.action_sd_slip()
        loan.sudo().delivery_date = fields.Date.today()
        with self.assertRaises(ValidationError):
            loan.action_move_to_treasury()  # security deposit not received yet
        Installment = self.env['microfinance.installment'].with_user(self.cashier)
        self.assertEqual(Installment.create_microfinance_security_deposit(
            {'microfinance_request_no': loan.name, 'amount': 1})['status'], 'error')
        result = Installment.create_microfinance_security_deposit({'microfinance_request_no': loan.name, 'amount': 5000})
        self.assertEqual(result['status'], 'success')
        loan.sd_slip_id = result['deposit_id']
        loan.action_move_to_treasury()
        bill = loan.sudo().bill_ids  # the loan officer has no accounting rights
        self.assertEqual(bill.amount_total, loan.total_amount, 'no tax on the loan amount')

        bill = bill.with_user(self.accountant)
        bill.action_post()
        Register = self.env['account.payment.register'].with_user(self.accountant)
        # another bill paid with the loan's name as memo does not complete it
        other = self.env['account.move'].with_user(self.accountant).create({
            'move_type': 'in_invoice', 'partner_id': self.donee.id, 'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {'name': 'Other', 'quantity': 1, 'price_unit': 10, 'tax_ids': [(5, 0, 0)]})]})
        other.action_post()
        Register.with_context(active_model='account.move', active_ids=other.ids).create(
            {'communication': loan.name}).action_create_payments()
        self.assertEqual(loan.state, 'treasury')
        # a partial payment of the loan's bill neither
        Register.with_context(active_model='account.move', active_ids=bill.ids).create(
            {'amount': bill.amount_total / 2}).action_create_payments()
        self.assertEqual(loan.state, 'treasury')
        # paid in full: done
        Register.with_context(active_model='account.move', active_ids=bill.ids).create({}).action_create_payments()
        self.assertEqual(loan.state, 'done')
        self.assertEqual(len(loan.microfinance_line_ids), 12)
        self.assertAlmostEqual(sum(loan.microfinance_line_ids.mapped('amount')), loan.total_amount)
        with self.assertRaises(AccessError):
            loan.with_user(self.auditor).write({'remarks': 'x'})

    def test_asset_loan_delivery_recovery_and_write_off(self):
        loan = self._loan(self.bike_line, self.bike_product_line)
        loan.sudo().warehouse_location_id = self.warehouse.lot_stock_id
        loan.action_proceed()
        self.assertEqual(loan.state, 'wfd')
        picking = loan.sudo().picking_ids.with_user(self.storekeeper)
        picking.move_ids.write({'quantity': 1, 'picked': True})
        picking.with_context(skip_sms=True).button_validate()
        self.assertEqual(loan.state, 'done')
        self.assertEqual(len(loan.microfinance_line_ids), 10)

        self._set_overdue(loan.microfinance_line_ids[-1], 61)
        loan.action_send_to_recovery()
        with self.assertRaises(UserError):
            loan.action_send_to_recovery()
        action = loan.with_user(self.recovery).action_temp_recovered()
        self.env['return.microfinance.product'].with_user(self.recovery).with_context(action['context']).create({
            'product_id': self.bike.id, 'destination_location_id': self.warehouse.lot_stock_id.id,
        }).action_recovery_done()
        receipt = loan.sudo().picking_ids.filtered(lambda p: p.picking_type_code == 'incoming')
        receipt.move_ids.write({'quantity': 1, 'picked': True})
        receipt.with_user(self.storekeeper).with_context(skip_sms=True).button_validate()
        self.assertEqual(loan.state, 'recover')

        loan.with_user(self.recovery).action_fully_recovered()
        loan.sudo().remarks = 'cannot pay'
        loan.with_user(self.recovery).request_write_off()
        with self.assertRaises(AccessError):
            loan.with_user(self.write_off_2).action_right_of_granted()
        loan.with_user(self.write_off_1).action_right_of_granted()
        loan.with_user(self.write_off_2).action_right_of_granted()
        self.assertEqual(loan.state, 'right_granted')

    def test_pdc_upload_only_own_installments(self):
        import base64
        import io
        import openpyxl
        loan = self._loan(self.cash_line, self.cash_product_line)
        loan.action_move_to_treasury()
        loan.sudo()._complete_application()
        line = loan.microfinance_line_ids[0]
        workbook = openpyxl.Workbook()
        workbook.active.append(['Installment ID', 'Cheque Number', 'Bank Name', 'Amount', 'Cheque Date'])
        workbook.active.append([line.id, 'CHQ-1', 'HBL', line.amount, fields.Date.today()])
        buffer = io.BytesIO()
        workbook.save(buffer)
        loan.write({'pdc_attachment': base64.b64encode(buffer.getvalue()), 'pdc_attachment_name': 'pdc.xlsx'})
        loan.action_upload_cheques()
        self.assertEqual((line.cheque_no, line.bank_name, line.cheque_date), ('CHQ-1', 'HBL', fields.Date.today()))

        workbook.active.append([line.id + 100000, 'CHQ-2', 'X', 1, fields.Date.today()])
        buffer = io.BytesIO()
        workbook.save(buffer)
        loan.write({'pdc_attachment': base64.b64encode(buffer.getvalue())})
        with self.assertRaises(ValidationError):
            loan.action_upload_cheques()

    def test_pos_cheque_updates_pdc_and_recovery_copies_status(self):
        loan = self._loan(self.cash_line, self.cash_product_line)
        loan.action_move_to_treasury()
        loan.sudo()._complete_application()
        line = loan.microfinance_line_ids[0]
        pdc = self.env['microfinance.pdc.line'].create({
            'microfinance_id': loan.id, 'microfinance_line_id': line.id, 'cheque_no': 'CHQ-T1'})
        bank = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        cheque = self.env['pos.cheque'].create({'name': 'CHQ-T1', 'bank_id': bank.id})
        cheque.action_clear()
        self.assertEqual((pdc.state_cheque, line.state, line.paid_amount), ('cleared', 'paid', line.amount))
        line2 = loan.microfinance_line_ids[1]
        pdc2 = self.env['microfinance.pdc.line'].create({
            'microfinance_id': loan.id, 'microfinance_line_id': line2.id, 'cheque_no': 'CHQ-T2'})
        self.env['pos.cheque'].create({'name': 'CHQ-T2', 'bank_id': bank.id}).action_bounce()
        self.assertEqual((pdc2.state_cheque, line2.state, line2.paid_amount), ('bounced', 'unpaid', 0))

        line.write({'paid_amount': line.amount, 'state': 'paid'})
        self._set_overdue(loan.microfinance_line_ids[-1], 61)
        loan.action_send_to_recovery()
        self.assertEqual(loan.state, 'in_recovery')
        self.assertEqual(loan.microfinance_recovery_line_ids[0].state, 'paid')
        self.assertEqual(loan.microfinance_recovery_line_ids[1].state, 'unpaid')
