from odoo import models


# pos.session._is_restricted_product() result -> slip type used on the closing screen
SLIP_TYPES = {1: 'restricted', 2: 'unrestricted', 0: 'neutral'}


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        res = super()._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

        # anything but True means the session was not closed (unbalanced entry)
        if res is True and lines:
            self._set_cheque_deposit_bank(lines)

        return res

    def _set_cheque_deposit_bank(self, lines):
        """Copy the bank selected on the closing screen to the cheques of this
        session (Treasury > POS Cheque > Deposit to Bank). A cleared cheque
        keeps its bank, same as on the list where it is readonly by then."""
        self.ensure_one()
        slips = {int(pm_id): vals or {} for pm_id, vals in lines.items()}

        for order in self.order_ids.filtered(lambda o: o.pos_cheque_id.state in ('draft', 'bounce')):
            bank_id = self._get_cheque_deposit_bank(order, slips)
            if bank_id:
                order.pos_cheque_id.bank_id = bank_id

    def _get_cheque_deposit_bank(self, order, slips):
        """Bank of the slip the order falls under: its payment method and its
        restricted / unrestricted / non-donation type."""
        amounts = {}
        for line in order.lines:
            slip_type = SLIP_TYPES[self._is_restricted_product(line.product_id)]
            amounts[slip_type] = amounts.get(slip_type, 0.0) + line.price_subtotal_incl

        # an order mixing types is one cheque all the same: biggest part wins
        for payment in order.payment_ids.sorted('amount', reverse=True):
            pm_slips = slips.get(payment.payment_method_id.id) or {}
            for slip_type in sorted(amounts, key=amounts.get, reverse=True):
                for slip in pm_slips.get(slip_type) or []:
                    bank = slip.get('bank')
                    if bank and str(bank) != '0':
                        return int(bank)

        return False
