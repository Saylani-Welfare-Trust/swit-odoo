# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDirectDepositPosLink(TransactionCase):
    """A direct deposit recorded at the POS carries the cashier's session,
    POS and cashier; what its clearing creates later (advance donation
    receipts ...) carries the same, and shows under the session's POS
    Documents."""

    def test_deposit_and_its_receipts_link_the_session(self):
        cashier = self.env['res.users'].create({
            'name': 'DD Cashier', 'login': 'dd_cashier',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('point_of_sale.group_pos_user').id,
                                  self.env.ref('bn_direct_deposit.direct_deposit_pos_action_group').id])]})
        config = self.env['pos.config'].create({'name': 'DD Shop'})
        session = self.env['pos.session'].create({'config_id': config.id, 'user_id': cashier.id})
        donor = self.env['res.partner'].create({'name': 'DD Donor'})
        product = self.env['product.template'].create({
            'name': 'DD Advance Donation', 'is_advance_donation': True, 'list_price': 500}).product_variant_id

        bank = self.env['account.journal'].search([('type', '=', 'bank')], limit=1) or \
            self.env['account.journal'].create({'name': 'DD Bank', 'code': 'DDBK', 'type': 'bank'})
        result = self.env['direct.deposit'].with_user(cashier).create_dd_record({
            'donor_id': donor.id, 'transaction_ref': 'DD-LINK-1', 'bank_id': bank.id,
            'order_lines': [{'product_id': product.id, 'quantity': 1, 'price': 500}]})
        self.assertEqual(result['status'], 'success', result)
        deposit = self.env['direct.deposit'].browse(result['id'])
        self.assertEqual((deposit.pos_session_id, deposit.pos_config_id, deposit.pos_cashier_id),
                         (session, config, cashier))

        # (Clear also posts the invoice: this database has no chart of accounts)
        receipts = deposit._create_advance_donation_receipts()
        self.assertTrue(receipts)
        for receipt in receipts:
            self.assertEqual((receipt.pos_session_id, receipt.pos_config_id, receipt.pos_cashier_id),
                             (session, config, cashier))

        action = session.action_view_pos_documents()
        rows = self.env['pos.document'].search(action['domain'])
        self.assertEqual(set(rows.mapped('res_model')) >= {'direct.deposit', 'advance.donation.receipt'}, True)
        self.assertEqual(config.pos_document_count, session.pos_document_count)
