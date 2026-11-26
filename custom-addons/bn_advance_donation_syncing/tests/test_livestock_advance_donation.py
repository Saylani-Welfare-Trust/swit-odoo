# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLivestockAdvanceDonation(TransactionCase):
    """An approved livestock contract creates its animals in Livestock Slaughter;
    slaughtering them disburses the contract line, not before its date."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.goat = cls.env['product.product'].create({'name': 'Goat AD', 'list_price': 1000, 'type': 'product'})
        cls.goat.product_tmpl_id.write({'is_livestock': True, 'is_advance_donation': True})
        cls.rice = cls.env['product.product'].create({'name': 'Rice AD', 'list_price': 100})
        cls.rice.product_tmpl_id.is_advance_donation = True
        cls.category = cls.env['advance.donation.category'].create({'name': 'Cat AD'})
        cls.donor = cls.env['res.partner'].create({'name': 'Donor AD'})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        categories = ({'allowed_product_category_ids': [(6, 0, cls.goat.categ_id.ids)]}
                      if 'allowed_product_category_ids' in Users._fields else {})

        def user(login, *groups, **extra):
            group_ids = [ref(g, raise_if_not_found=False) for g in ('base.group_user',) + groups]
            return Users.create(dict(categories, name=login, login=login, email=login + '@example.com',
                                     groups_id=[(6, 0, [g.id for g in group_ids if g])], **extra))
        # (national access: the test is about the contract, not about Branch / Site rules)
        cls.approver_1 = user('ls_ad_ap1', 'bn_advance_donation.group_adv_don_approval_1', all_nodes=True)
        cls.approver_2 = user('ls_ad_ap2', 'bn_advance_donation.group_adv_don_approval_2', all_nodes=True)
        cls.butcher = user('ls_ad_user', 'bn_livestock_slaugther.livestock_slaugther_user_group',
                           'stock.group_stock_user', 'bn_stock_location.stock_scope_unrestricted_group',
                           all_nodes=True)
        cls.Slaughter = cls.env['livestock.slaugther']

    def _approved(self, product, contract_type='product', **vals):
        donation = self.env['advance.donation'].create(dict({
            'donor_id': self.donor.id, 'category_id': self.category.id, 'contract_type': contract_type,
            'product_id': product.id, 'amount_percentage': 100, 'total_no_of_product': 2}, **vals))
        donation.compute_donation()
        donation.action_send_for_approval()
        donation.with_user(self.approver_1).action_approved()
        self.assertFalse(self.Slaughter.search_count([('advance_donation_id', '=', donation.id)]),
                         'nothing before the final approval')
        donation.with_user(self.approver_2).action_approved()
        self.assertEqual(donation.state, 'approved')
        animals = self.Slaughter.search([('advance_donation_id', '=', donation.id)])
        # they wait in their warehouse: slaughtered there once it is a slaughter location
        animals.mapped('transfer_location').sudo().write({'is_slaughter_location': True})
        return donation, animals

    def test_quantity_contract(self):
        donation, records = self._approved(self.goat)
        self.assertEqual(len(records), 2, 'one animal per line')
        for line in donation.advance_donation_lines:
            record = records.filtered(lambda r: r.advance_donation_line_id == line)
            self.assertEqual(len(record), 1)
            self.assertEqual(record.state, 'not_received')
            self.assertEqual((record.product_id, record.donee_id, record.ref), (self.goat, self.donor, donation.name))
            self.assertEqual((record.price, record.advance_donation_amount), (line.amount, line.amount))
            self.assertEqual(record.order_date, line.date)
            self.assertTrue(line.is_reserved)
            self.assertFalse(line.is_disbursed)
        donation._create_livestock_slaughter_records()
        self.assertEqual(self.Slaughter.search_count([('advance_donation_id', '=', donation.id)]), 2, 'created once')

        record = records[0]
        record.with_user(self.butcher).action_confirm()
        line = record.advance_donation_line_id
        self.assertEqual(record.state, 'slaughtered')
        self.assertTrue(line.is_disbursed)
        self.assertEqual(line.disbursed_amount, line.amount)
        disbursement = self.env['advance.donation.disbursement.line'].search([('advance_donation_line_id', '=', line.id)])
        self.assertEqual((len(disbursement), disbursement.disbursed_record), (1, record.name))
        self.assertFalse(donation.is_fully_disbursed)
        (records - record).with_user(self.butcher).action_confirm()
        self.assertTrue(donation.is_fully_disbursed)

    def test_frequency_contract_and_line_date(self):
        today = fields.Date.today()
        donation, animals = self._approved(self.goat, 'frequency', contract_frequency='daily', no_of_product=3,
                                           contract_start_date=today, contract_end_date=today + timedelta(days=1))
        line, tomorrow_line = donation.advance_donation_lines.sorted('date')
        todays = animals.filtered(lambda r: r.advance_donation_line_id == line)
        self.assertEqual((len(animals), len(todays)), (6, 3))
        for index, animal in enumerate(todays):
            animal.with_user(self.butcher).action_confirm()
            self.assertEqual(line.is_disbursed, index == 2, "disbursed with its last animal")
        tomorrows = animals.filtered(lambda r: r.advance_donation_line_id == tomorrow_line)[:1]
        with self.assertRaisesRegex(UserError, 'can only be slaughtered from'):
            tomorrows.with_user(self.butcher).action_confirm()
        self.assertEqual(tomorrows.state, 'not_received')
        self.assertFalse(tomorrow_line.disbursed_amount)

    def test_not_livestock_and_open_contract(self):
        donation, animals = self._approved(self.rice)
        self.assertFalse(animals)
        open_contract, animals = self._approved(self.goat, 'open_contract', total_product_amount=5000)
        self.assertFalse(animals)
