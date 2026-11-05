from datetime import timedelta
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    donor_receipt_state = fields.Selection(
        [('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Not Needed')],
        string='Donor Receipt (WhatsApp / SMS)', copy=False, index='btree_not_null', readonly=True)
    donor_receipt_result = fields.Char('Donor Receipt Result', copy=False, readonly=True)

    @api.model  
    def sms_or_whatsapp_send_receipt(self, order_id):
        _logger.info('WHATSAPP: whatsapp_send_receipt called')
        return self.send_whatsapp_after_payment(order_id)

    def send_whatsapp_after_payment(self, order_id):
        """Donation receipt to the donor: WhatsApp first, SMS fallback
        (bn.donor.notifier)."""
        if isinstance(order_id, list):
            order_id = order_id[0] if order_id else None
        order = self.browse(int(order_id)).exists() if order_id else None
        if not order:
            return {'status': 'error', 'message': 'Order not found'}
        if not order.partner_id:
            return {'status': 'error', 'message': 'No customer selected'}
        if order.donor_receipt_state == 'sent':
            return {'status': 'skipped', 'message': 'The donor receipt was already sent'}

        def sms_message(link):
            text = (
                f"Thank you for donation of Rs. {order.amount_total}. "
                f"{order.user_id.branch_code}-"
                f"{order.date_order.year if order.date_order else ''}-"
                f"{order.pos_order_seq} to Saylani Welfare Trust. "
                f"Your generosity will make an immediate difference in the lives of needy families."
            )
            return text + (f"\n\nReceipt: {link}" if link else '')

        result = self.env['bn.donor.notifier']._send(
            order, order.partner_id, sms_message,
            report_name='bn_pos_order.pos_whatsapp_donation_receipt_template',
            filename=f"Receipt_{order.name.replace('/', '_')}.pdf")
        order.sudo().write({
            'donor_receipt_state': 'failed' if result['status'] == 'error' else 'sent',
            'donor_receipt_result': result['message'],
        })
        return result

    @api.model
    def _cron_send_missing_donor_receipts(self, limit=50):
        """Safety net: the POS screen asks for the receipt a few seconds after
        payment. When that call never arrived (screen closed, offline ...),
        the receipt of a paid donation still goes out from here. Orders the
        POS holds back (cheque not cleared yet) answer 'skipped' and are not
        asked again."""
        now = fields.Datetime.now()
        orders = self.search([
            ('donor_receipt_state', '=', False),
            ('partner_id', '!=', False),
            ('amount_total', '>', 0),
            ('state', 'in', ('paid', 'done', 'invoiced')),
            ('create_date', '<', now - timedelta(minutes=10)),
            ('create_date', '>', now - timedelta(days=2)),
        ], order='id', limit=limit)
        for order in orders:
            try:
                with self.env.cr.savepoint():
                    result = order.sms_or_whatsapp_send_receipt(order.id)
                    if result.get('status') == 'skipped' and not order.donor_receipt_state:
                        order.write({'donor_receipt_state': 'skipped',
                                     'donor_receipt_result': result.get('message')})
                self.env.cr.commit()
            except Exception as e:  # noqa: BLE001 - next order
                _logger.error('POS order %s: donor receipt failed: %s', order.name, e)
