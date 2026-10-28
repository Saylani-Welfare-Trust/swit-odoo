import logging

from odoo import api, models

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
            result, collection, issuance = KeyIssuance._bn_check_donation_box(box_data)
            if result.get('status') == 'success':
                KeyIssuance._bn_apply_donation_box(collection, issuance, box_data)
            else:
                # already closed (order synced twice) or changed meanwhile
                _logger.warning("POS order %s: donation box not closed: %s", pos_order.name, result.get('body'))
        return order_id
