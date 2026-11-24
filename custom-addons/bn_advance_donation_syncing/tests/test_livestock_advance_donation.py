# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLivestockAdvanceDonation(TransactionCase):
    """An approved livestock contract creates its animals in Livestock Slaughter;
    slaughtering them disburses the contract line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.goat = cls.env['product.product'].create({
            'name': 'Goat AD', 'list_price': 1000, 'detailed_type': 'product',
            'is_advance_donation': True})
        # the product variant's flags follow the template
        cls.goat.product_tmpl_id.write({'is_livestock': True, 'is_advance_donation': True})
        cls.rice = cls.env['product.product'].create({
            'name': 'Rice AD', 'list_price': 100})
        cls.rice.product_tmpl_id.is_advance_donation = True
        cls.category = cls.env['advance.donation.category'].create({'name': 'Cat AD'})
        cls.donor = cls.env['res.partner'].create({'name': 'Donor AD'})
        Users = cls.env['res.users']
        categories = ({'allowed_product_category_ids': [(6, 0, cls.goat.categ_id.ids)]}
                      if 'allowed_product_category_ids' in Users._fields else {})

        def user(login, *groups):
            group_ids = [ref(g, raise_if_not_found=False) for g in ('base.group_user',) + groups]
            return Users.create(dict(categories, name=login, login=login, groups_id=[
                (6, 0, [g.id for g in group_ids if g])]))
        cls.approver_1 = user('ls_ad_ap1', 'bn_advance_donation.group_adv_don_approval_1')
        cls.approver_2 = user('ls_ad_ap2', 'bn_advance_donation.group_adv_don_approval_2')
        # unrestricted stock scope where that group exists: the test is about the
        # disbursement, not about the user's allowed locations
        cls.butcher = user('ls_ad_user', 'bn_livestock_slaugther.livestock_slaugther_user_group',
                           'stock.group_stock_user', 'bn_stock_location.stock_scope_unrestricted_group')
        cls.Slaughter = cls.env['livestock.slaugther']
        assert cls.goat.is_livestock and not cls.rice.is_livestock

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
        return donation

    def test_quantity_contract(self):
        donation = self._approved(self.goat)
        records = self.Slaughter.search([('advance_donation_id', '=', donation.id)])
        self.assertEqual(len(records), 2, 'one animal per line')
        for line in donation.advance_donation_lines:
            record = records.filtered(lambda r: r.advance_donation_line_id == line)
            self.assertEqual(len(record), 1)
            self.assertEqual(record.state, 'not_received')
            self.assertEqual((record.product_id, record.donee_id, record.ref), (self.goat, self.donor, donation.name))
            self.assertEqual(record.price, line.amount)
            self.assertEqual(record.advance_donation_amount, line.amount)
            self.assertTrue(line.is_reserved)
            self.assertFalse(line.is_disbursed)

        # approving again (or any rerun) creates nothing more
        donation._create_livestock_slaughter_records()
        self.assertEqual(self.Slaughter.search_count([('advance_donation_id', '=', donation.id)]), 2)

        record = records[0]
        record.with_user(self.butcher).action_confirm()
        line = record.advance_donation_line_id
        self.assertEqual(record.state, 'received')
        self.assertTrue(line.is_disbursed)
        self.assertEqual(line.disbursed_amount, line.amount)
        disbursement = self.env['advance.donation.disbursement.line'].search([('advance_donation_line_id', '=', line.id)])
        self.assertEqual(len(disbursement), 1)
        self.assertEqual((disbursement.disbursed_amount, disbursement.disbursed_record), (line.amount, record.name))
        self.assertFalse((records - record).advance_donation_line_id.is_disbursed, 'the other animal is not slaughtered yet')
        self.assertFalse(donation.is_fully_disbursed)
        (records - record).with_user(self.butcher).action_confirm()
        self.assertTrue(donation.is_fully_disbursed)

        # confirming again does not disburse twice
        record.with_user(self.butcher).action_confirm()
        self.assertEqual(self.env['advance.donation.disbursement.line'].search_count(
            [('advance_donation_line_id', '=', line.id)]), 1)

    def test_frequency_contract_line_disbursed_with_its_last_animal(self):
        today = fields.Date.today()
        donation = self._approved(self.goat, 'frequency', contract_frequency='daily', no_of_product=3,
                                  contract_start_date=today, contract_end_date=today + timedelta(days=1))
        line, tomorrow_line = donation.advance_donation_lines.sorted('date')
        self.assertEqual((len(donation.advance_donation_lines), line.quantity), (2, 3))
        animals = self.Slaughter.search([('advance_donation_line_id', '=', line.id)])
        self.assertEqual(len(animals), 3)
        self.assertAlmostEqual(sum(animals.mapped('price')), line.amount)
        self.assertEqual(self.Slaughter.search_count([('advance_donation_id', '=', donation.id)]), 6)
        for index, animal in enumerate(animals):
            animal.with_user(self.butcher).action_confirm()
            self.assertEqual(line.is_disbursed, index == 2)
        self.assertAlmostEqual(line.disbursed_amount, line.amount)

        # tomorrow's animals are not slaughtered before their date
        tomorrow_animal = self.Slaughter.search([('advance_donation_line_id', '=', tomorrow_line.id)], limit=1)
        self.assertEqual(tomorrow_animal.advance_donation_date, today + timedelta(days=1))
        with self.assertRaises(UserError):
            tomorrow_animal.with_user(self.butcher).action_confirm()
        self.assertEqual(tomorrow_animal.state, 'not_received')
        self.assertFalse(tomorrow_line.disbursed_amount)

    def test_not_livestock_and_open_contract(self):
        donation = self._approved(self.rice)
        self.assertFalse(self.Slaughter.search_count([('advance_donation_id', '=', donation.id)]))
        self.assertFalse(donation.advance_donation_lines.filtered('is_reserved'))
        open_contract = self._approved(self.goat, 'open_contract', total_product_amount=5000)
        self.assertFalse(self.Slaughter.search_count([('advance_donation_id', '=', open_contract.id)]))
