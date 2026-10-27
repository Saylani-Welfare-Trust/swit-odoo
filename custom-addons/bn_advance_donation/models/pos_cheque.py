from odoo import fields, models


class POSCheque(models.Model):
    _inherit = 'pos.cheque'

    def _create_advance_donation_receipts(self):
        """Advance donation lines of the linked POS order get their paid
        advance.donation.receipt when the cheque is cleared - not when the
        cheque was received (see advance.donation.receipt.register_pos_payment)."""
        self.ensure_one()
        Receipt = self.env['advance.donation.receipt'].sudo()
        created = Receipt
        pos_order = self._get_pos_order()
        lines = pos_order.lines.filtered(lambda l: l.product_id.is_advance_donation and l.price_subtotal_incl > 0)
        for line in lines:
            if Receipt.search_count([('order_id', '=', pos_order.id), ('product_id', '=', line.product_id.id),
                                     ('cheque_number', '=', self.name)]):
                continue  # already created (cheque cleared before)
            created |= Receipt.create({
                'donor_id': self.donor_id.id,
                'amount': line.price_subtotal_incl,
                'product_id': line.product_id.id,
                'payment_type': 'cheque',
                'cheque_number': self.name,
                'cheque_date': self.date,
                'date': fields.Date.today(),
                'order_id': pos_order.id,
                'remarks': 'Auto-created from POS Cheque %s' % self.name,
                'state': 'paid',
            })
        return created

    def action_clear(self):
        res = super().action_clear()
        for rec in self:
            rec._create_advance_donation_receipts()
        return res
