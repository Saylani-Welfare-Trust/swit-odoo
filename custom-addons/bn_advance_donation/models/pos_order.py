from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Cash advance donations get their paid receipt as soon as the POS
        order is saved. Cheque ones get it when the cheque is cleared
        (pos.cheque.action_clear)."""
        order_id = super()._process_order(order, draft, existing_order)
        pos_order = self.browse(order_id)
        if pos_order.state in ('paid', 'done', 'invoiced'):
            pos_order.sudo()._create_cash_advance_donation_receipts()
        return order_id

    def _is_paid_in_cash(self):
        self.ensure_one()
        payment_method = self.payment_ids[:1].payment_method_id
        return bool(payment_method) and (payment_method.is_cash_count or 'cash' in (payment_method.name or '').lower())

    def _create_cash_advance_donation_receipts(self):
        Receipt = self.env['advance.donation.receipt']
        created = Receipt
        for order in self:
            donation_lines = order.lines.filtered(
                lambda l: l.product_id.is_advance_donation and l.price_subtotal_incl > 0
            )
            if not donation_lines or not order._is_paid_in_cash():
                continue
            # receipts already linked to this order (by link or POS reference)
            if Receipt.search_count(['|', ('order_id', '=', order.id), ('pos_reference', '=', order.pos_reference)]):
                continue
            for line in donation_lines:
                receipt = Receipt.create({
                    'payment_type': 'cash',
                    'amount': line.price_subtotal_incl,
                    'product_id': line.product_id.id,
                    'donor_id': order.partner_id.id,
                    'date': order.date_order.date() if order.date_order else fields.Date.today(),
                    'order_id': order.id,
                    'pos_order_id': order.id,
                    'pos_session_id': order.session_id.id,
                    'pos_reference': order.pos_reference,
                    'remarks': f'From POS Order {order.name}',
                })
                receipt.action_paid()
                created |= receipt
        return created

    def action_sync_advance_donation_receipts(self):
        """Backfill advance.donation.receipt records for cash POS orders that
        sold an advance-donation product but never got a receipt."""
        orders = self if self else self.search([
            ('lines.product_id.is_advance_donation', '=', True),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ])
        created = orders.sudo()._create_cash_advance_donation_receipts()
        _logger.info("Advance donation receipt sync: created %s receipt(s).", len(created))
        return created
