import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class POSOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Medical equipment payments are applied once the order is saved
        (not from the POS before validation, which would update the request
        even when the order never reaches the server)."""
        order_id = super()._process_order(order, draft, existing_order)
        me_data = ((order.get('data') or {}).get('extra_data') or {}).get('medical_equipment')
        pos_order = self.browse(order_id)
        if me_data and pos_order.state in ('paid', 'done', 'invoiced'):
            pos_order.sudo()._apply_medical_equipment_payment(me_data)
        return order_id

    def _apply_medical_equipment_payment(self, me_data):
        self.ensure_one()
        Equipment = self.env['medical.equipment']

        # receiving popup: payment / refund of an equipment request
        if me_data.get('equipment_id'):
            equipment = Equipment.browse(me_data['equipment_id']).exists()
            if equipment.state == 'donate':
                equipment.remaining_amount = 0
            elif equipment.state == 'sd_received':
                equipment.state = 'payment_received'
            elif equipment.state == 'refund':
                equipment.state = 'payment_return'
            return

        # provisional popup: security deposit of an approved request
        equipment = Equipment.browse(me_data.get('medical_equipment_id') or []).exists()
        if not equipment:
            return
        cheque = self.pos_cheque_id
        deposit = equipment._get_security_deposit()
        if deposit.state == 'paid' or (cheque and deposit and cheque.medical_security_deposit_id == deposit
                                       and deposit.state == 'pending'):
            return  # order synced twice
        if equipment.state not in ('cfo_approval', 'approved'):
            _logger.warning("POS order %s: security deposit of %s not recorded, request in status %s",
                            self.name, equipment.name, equipment.state)
            return
        deposit = equipment._receive_security_deposit('pending' if cheque else 'paid', {
            'amount': self.amount_total,
            'payment_method': 'cheque' if cheque else 'cash',
            'bank_name': self.bank_name or False,
            'cheque_no': self.cheque_number or False,
            'cheque_date': self.cheque_date or False,
            'date': self.date_order.date() if self.date_order else fields.Date.today(),
        })
        if cheque and not cheque.medical_security_deposit_id:
            cheque.medical_security_deposit_id = deposit
