import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class POSOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        """The donation box collection is closed once its POS order is saved
        (not from the POS before validation)."""
        order_id = super()._process_order(order, draft, existing_order)
        box_data = ((order.get('data') or {}).get('extra_data') or {}).get('donation_box')
        pos_order = self.browse(order_id)
        if box_data and pos_order.state in ('paid', 'done', 'invoiced'):
            KeyIssuance = self.env['key.issuance'].sudo()
            result, collection, issuance = KeyIssuance._check_donation_box(box_data)
            if result.get('status') == 'success':
                KeyIssuance._apply_donation_box(collection, issuance, box_data)
                pos_order._link_rider_collection(collection.id)
                # the receipt the donor got for this collection
                collection.sudo().pos_receipt_number = (
                    box_data.get('receipt_number')
                    or ('dn_number' in pos_order._fields and pos_order.dn_number)
                    or pos_order.pos_reference or pos_order.name)
            else:
                # already closed (order synced twice) or changed meanwhile
                _logger.warning("POS order %s: donation box not closed: %s", pos_order.name, result.get('body'))
        return order_id

    def _link_rider_collection(self, collection_id):
        """Keep on the rider collection the POS order that paid it and its DN #."""
        self.ensure_one()
        collection = self.env['rider.collection'].sudo().browse(collection_id).exists()
        if collection and not collection.pos_order_id:
            collection.write({'pos_order_id': self.id, 'dn_number': self._dn_number()})

    def _dn_number(self):
        """DN # as printed on the POS receipt: <branch code>-C<counter>-<year>-<POS order seq>."""
        self.ensure_one()
        # bn_livestock_slaugther, when installed, already stores it on every order when paid
        if 'dn_number' in self._fields and self.dn_number:
            return self.dn_number
        year = fields.Datetime.context_timestamp(self, self.date_order).year
        return '%s-C%s-%s-%s' % (
            ('branch_code' in self.user_id._fields and self.user_id.branch_code) or 'UNK',
            ('counter' in self.config_id._fields and self.config_id.counter) or 0,
            year,
            ('pos_order_seq' in self._fields and self.pos_order_seq) or '0000',
        )
