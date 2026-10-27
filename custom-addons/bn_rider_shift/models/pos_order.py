from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        # The POS Donation Box popup puts the paid rider collection in extra_data.
        box_data = ((order.get('data') or {}).get('extra_data') or {}).get('donation_box') or {}
        if not draft and box_data.get('collection_id'):
            self.browse(order_id)._bn_link_rider_collection(box_data['collection_id'])
        return order_id

    def _bn_link_rider_collection(self, collection_id):
        """Keep on the rider collection the POS order that paid it and its DN #."""
        self.ensure_one()
        collection = self.env['rider.collection'].sudo().browse(collection_id).exists()
        if collection and not collection.pos_order_id:
            collection.write({'pos_order_id': self.id, 'dn_number': self._bn_dn_number()})

    def _bn_dn_number(self):
        """DN # as printed on the POS receipt: <branch code>-C<counter>-<year>-<POS order seq>."""
        self.ensure_one()
        year = fields.Datetime.context_timestamp(self, self.date_order).year
        return '%s-C%s-%s-%s' % (
            self.user_id.branch_code or 'UNK',
            self.config_id.counter or 0,
            year,
            self.pos_order_seq or '0000',
        )
