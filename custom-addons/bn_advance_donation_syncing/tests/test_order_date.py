# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSlaughterOrderDate(TransactionCase):
    """The Order Date of a slaughter line: its POS order's date, or for a line
    funded by an advance donation the date of its contract line."""

    def test_advance_donation_order_date(self):
        env = self.env
        goat = env['product.product'].create({'name': 'OD Goat', 'list_price': 1000})
        goat.product_tmpl_id.is_advance_donation = True
        day = fields.Date.today() + timedelta(days=3)
        donation = env['advance.donation'].create({
            'donor_id': env['res.partner'].create({'name': 'OD Donor'}).id,
            'category_id': env['advance.donation.category'].create({'name': 'OD Cat'}).id,
            'contract_type': 'frequency', 'contract_frequency': 'daily', 'no_of_product': 1,
            'contract_start_date': day, 'contract_end_date': day,
            'product_id': goat.id, 'amount_percentage': 100})
        donation.compute_donation()
        line = donation.advance_donation_lines
        self.assertEqual(line.date, day)
        record = env['livestock.slaugther'].create({'product_id': goat.id, 'quantity': 1})
        self.assertFalse(record.order_date, "no order yet")
        record.write({'advance_donation_id': donation.id, 'advance_donation_line_id': line.id})
        self.assertEqual(record.order_date, day, "the date of its contract line")
        line.date = False
        self.assertEqual(record.order_date, fields.Date.context_today(record, donation.create_date),
                         "else the day the contract was made")

    def test_pos_order_date(self):
        env = self.env
        journal = env['account.journal'].create({'name': 'OD Cash', 'code': 'ODC', 'type': 'cash'})
        method = env['pos.payment.method'].create({'name': 'OD Cash', 'journal_id': journal.id})
        config = env['pos.config'].create({'name': 'OD Shop', 'payment_method_ids': [(6, 0, method.ids)]})
        session = env['pos.session'].create({'config_id': config.id, 'user_id': env.uid})
        order = env['pos.order'].create({'session_id': session.id, 'amount_tax': 0, 'amount_total': 0,
                                         'amount_paid': 0, 'amount_return': 0,
                                         'date_order': '2026-11-20 10:00:00'})
        record = env['livestock.slaugther'].create({'product_id': env['product.product'].create({'name': 'OD Cow'}).id,
                                                    'quantity': 1, 'pos_order_id': order.id})
        self.assertEqual(record.order_date, fields.Date.context_today(record, order.date_order))
        self.assertEqual(str(record.order_date), '2026-11-20')
