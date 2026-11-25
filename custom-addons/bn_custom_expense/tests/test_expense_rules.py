# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExpenseRules(TransactionCase):
    """The expense rules hold on every save, not only on the form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'Expense Employee'})
        cls.product = cls.env['product.product'].create({'name': 'Expense Taxi', 'can_be_expensed': True,
                                                          'standard_price': 0})

    def _vals(self, **kw):
        vals = {'name': 'Taxi', 'employee_id': self.employee.id, 'product_id': self.product.id,
                'total_amount_currency': 500, 'date': fields.Date.today()}
        vals.update(kw)
        return vals

    def test_valid_expense(self):
        expense = self.env['hr.expense'].create(self._vals(payment_mode='own_account'))
        self.assertEqual(expense.payment_mode, 'own_account')

    def test_company_paid_refused(self):
        with self.assertRaises(ValidationError):
            self.env['hr.expense'].create(self._vals(payment_mode='company_account'))
        expense = self.env['hr.expense'].create(self._vals())
        with self.assertRaises(ValidationError):
            expense.write({'payment_mode': 'company_account'})

    def test_dates_refused(self):
        today = fields.Date.today()
        with self.assertRaises(ValidationError):
            self.env['hr.expense'].create(self._vals(date=today + timedelta(days=1)))
        with self.assertRaises(ValidationError):
            self.env['hr.expense'].create(self._vals(date=today - timedelta(days=91)))
