from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pos_cheque import POS_GROUP


class POSOrder(models.Model):
    _inherit = 'pos.order'


    pos_cheque_id = fields.Many2one('pos.cheque', string="POS Cheque")

    bank_name = fields.Char('Bank Name')
    cheque_number = fields.Char('Cheque No')
    qr_code = fields.Char('QR Code No.')
    
    cheque_date = fields.Date('Date')

    bounce_count = fields.Integer(related='pos_cheque_id.bounce_count', string="Bounce Count", store=True)
    
    cheque_state = fields.Selection(related='pos_cheque_id.state', string="Cheque Status", store=True)


    def _order_fields(self, ui_order):
        res = super(POSOrder, self)._order_fields(ui_order)

        cheque_date = ui_order.get('cheque_date')
        parsed_date = False
        if cheque_date:
            try:
                parsed_date = fields.Date.to_date(cheque_date[:10])
            except Exception:
                parsed_date = False

        res.update({
            'bank_name': ui_order.get('bank_name') or False,
            'cheque_number': ui_order.get('cheque_number') or False,
            'qr_code': ui_order.get('qr_code') or False,
            'cheque_date': parsed_date,
        })

        # a cheque return ("Settle Order" in the POS Cheque popup) gives the
        # bounced cheque back: nothing for treasury to clear, it reaches
        # Journal Transfer through the session's deposit slip instead
        cheque_number = ui_order.get('cheque_number')
        if cheque_number and not ui_order.get('qr_code') and not ui_order.get('pos_cheque_order_id'):
            cheque_vals = self._prepare_pos_cheque_vals(ui_order, {
                'bank_name': ui_order.get('bank_name') or False,
                'name': cheque_number,
                'date': parsed_date,
            })
            # created for the cashier: POS users have no rights on pos.cheque
            res['pos_cheque_id'] = self.env['pos.cheque'].sudo().create(cheque_vals).id

        return res

    def _prepare_pos_cheque_vals(self, ui_order, vals):
        """Hook: program modules (bn_welfare, bn_medical_equipment ...) link
        the cheque to their record from ui_order['extra_data']."""
        return vals

    @api.model
    def sms_or_whatsapp_send_receipt(self, order_id):
        """POS calls this right after payment. A cheque order only has a
        provisional slip at that point: its receipt is sent when treasury
        clears the cheque (pos.cheque.action_clear)."""
        order = self.browse(order_id or [])[:1]
        if order.pos_cheque_id and order.pos_cheque_id.state != 'clear':
            return {'status': 'skipped', 'message': 'Receipt will be sent when the cheque is cleared'}
        if order.pos_cheque_order_id and order.cheque_number:
            return {'status': 'skipped', 'message': 'No receipt for a cheque return'}

        return super().sms_or_whatsapp_send_receipt(order_id)

    # ---------- POS Cheques popup (RPC) ----------
    STATUS_LABELS = {'draft': 'Pending', 'bounce': 'Bounce', 'clear': 'Cleared', 'cancel': 'Cancelled'}

    def _check_pos_cheque_access(self):
        if not self.env.user.has_group(POS_GROUP):
            raise AccessError(_('You are not allowed to manage POS cheques.'))

    def _cheque_order_domain(self, shop):
        # cheque returns carry the cheque number but have no pos.cheque
        return [('session_id.config_id', '=', shop), ('pos_cheque_id', '!=', False),
                ('cheque_state', 'not in', ['clear', 'cancel'])]

    def _cheque_order_data(self, orders):
        return [{
            "id": order.id,
            "name": order.name,
            "date": order.date_order,
            "ref": order.pos_reference,
            "customer": order.partner_id.name,
            "partner_id": order.partner_id.id,
            "amount": order.amount_total,
            "cheque_number": order.cheque_number,
            "bank_name": order.bank_name,
            "bounce_count": order.bounce_count,
            "status": self.STATUS_LABELS.get(order.cheque_state, order.cheque_state or ''),
        } for order in orders]

    @api.model
    def get_cheque_pos_order(self, shop, offset=0, limit=10):
        self._check_pos_cheque_access()
        Order = self.sudo()
        domain = self._cheque_order_domain(shop)
        orders = Order.search(domain, offset=offset, limit=limit)
        return {"orders": self._cheque_order_data(orders), "total_count": Order.search_count(domain)}

    @api.model
    def get_cheque_pos_order_specific(self, shop, text):
        self._check_pos_cheque_access()
        if not text:
            return self.get_cheque_pos_order(shop)
        orders = self.sudo().search(self._cheque_order_domain(shop) + [('cheque_number', '=', text.strip())])
        return {"orders": self._cheque_order_data(orders), "total_count": len(orders)}

    def _get_pos_cheque_order(self, orderid, shop=None):
        self._check_pos_cheque_access()
        order = self.sudo().browse(orderid).exists()
        if not order or not order.pos_cheque_id:
            raise UserError(_('This cheque order does not exist anymore.'))
        if shop and order.session_id.config_id.id != shop:
            raise UserError(_('This cheque was received at another POS.'))
        return order

    @api.model
    def redeposite_cheque(self, orderid, shop=None):
        order = self._get_pos_cheque_order(orderid, shop)
        order.pos_cheque_id.action_redeposit()
        return {"status": "success"}

    @api.model
    def settle_cheque_order(self, orderid):
        """Called once the return order of a bounced cheque is paid: the
        cheque is given back to the donor."""
        try:
            order = self._get_pos_cheque_order(orderid)
            order.pos_cheque_id.action_cancel()
        except (UserError, AccessError) as e:
            return {"status": "error", "body": str(e)}
        return {"status": "success", "body": _("Cheque Status has been updated successfully.")}
