from odoo import models, fields

import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_sync_advance_donation_receipts(self):
        """Backfill advance.donation.receipt records for POS orders that
        sold an advance-donation product by cash but never got a receipt
        (caused by a front-end bug that misclassified cash payments as
        cheque, which defers/skips receipt creation)."""
        Receipt = self.env['advance.donation.receipt']

        orders = self if self else self.search([
            ('lines.product_id.is_advance_donation', '=', True),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ])

        created = Receipt
        skipped = 0

        for order in orders:
            donation_lines = order.lines.filtered(
                lambda l: l.product_id.is_advance_donation and l.price_subtotal_incl > 0
            )
            if not donation_lines:
                continue

            # Already has a receipt linked from this order (new-style link).
            if Receipt.search_count([('order_id', '=', order.id)]):
                skipped += 1
                continue

            # Already has a receipt referenced via the printed source document.
            if order.source_document and Receipt.search_count([('name', '=', order.source_document)]):
                skipped += 1
                continue

            payment_method = order.payment_ids[:1].payment_method_id
            is_cash = bool(payment_method) and 'cash' in (payment_method.name or '').lower()
            if not is_cash:
                # Cheque/bank payments are backfilled separately when the
                # cheque is cleared - don't touch them here.
                continue

            for line in donation_lines:
                receipt = Receipt.create({
                    'payment_type': 'cash',
                    'amount': line.price_subtotal_incl,
                    'product_id': line.product_id.id,
                    'donor_id': order.partner_id.id if order.partner_id else False,
                    'date': order.date_order.date() if order.date_order else fields.Date.today(),
                    'order_id': order.id,
                    'pos_order_id': order.id,
                    'pos_session_id': order.session_id.id,
                    'remarks': f'Backfilled from POS Order {order.name}',
                })
                receipt.action_paid()
                created |= receipt

                if not order.source_document:
                    order.source_document = receipt.name

        _logger.info(
            f"Advance donation receipt sync: created {len(created)} receipt(s), "
            f"skipped {skipped} already-synced order(s)."
        )

        return created
