# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
from odoo import api, fields, models


class AccountRegisterPayments(models.TransientModel):
    """Inherits the account.payment.register model to add the cheque_date field"""
    _inherit = "account.payment.register"

    cheque_date = fields.Date(
        string="Cheque Date",
        copy=False,
        help="Date mentioned on the cheque"
    )

    def _prepare_payment_vals(self, invoices):
        """Prepare the payment values and include cheque_date"""
        res = super(AccountRegisterPayments, self)._prepare_payment_vals(invoices)
        if self.cheque_date:
            res.update({
                'cheque_date': self.cheque_date,
            })
        return res

    def _create_payment_vals_from_wizard(self, batch_result):
        """Super the wizard action to include cheque_date"""
        res = super(AccountRegisterPayments, self)._create_payment_vals_from_wizard(batch_result)
        if self.cheque_date:
            res.update({
                'cheque_date': self.cheque_date,
            })
        return res

    def _create_payment_vals_from_batch(self, batch_result):
        """Super the batch action to include cheque_date"""
        res = super(AccountRegisterPayments, self)._create_payment_vals_from_batch(batch_result)
        if self.cheque_date:
            res.update({
                'cheque_date': self.cheque_date,
            })
        return res

    def _create_payments(self):
        """Create payments and update cheque_date"""
        payments = super(AccountRegisterPayments, self)._create_payments()
        for payment in payments:
            if self.cheque_date:
                payment.write({
                    'cheque_date': self.cheque_date
                })
        return payments


class AccountPayment(models.Model):
    """Inherits the account.payment model to add cheque_date field"""
    _inherit = "account.payment"

    cheque_date = fields.Date(
        string="Cheque Date",
        copy=False,
        help="Date mentioned on the cheque"
    )
