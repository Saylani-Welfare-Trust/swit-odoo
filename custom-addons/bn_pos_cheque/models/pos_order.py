from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class POSOrder(models.Model):
    _inherit = 'pos.order'

    pos_cheque_id = fields.Many2one('pos.cheque', string="POS Cheque")

    bank_name = fields.Char('Bank Name')
    cheque_number = fields.Char('Cheque No')
    qr_code = fields.Char('QR Code No.')
    
    cheque_date = fields.Date('Date')

    bounce_count = fields.Integer(related='pos_cheque_id.bounce_count', string="Bounce Count", store=True)
    
    cheque_state = fields.Selection(related='pos_cheque_id.state', string="Cheque Status", store=True)
    extra_data = fields.Text('Extra Data', help="JSON data from POS session for reference linking")
    
    @api.model
    def create(self, vals):
        """Override create to link cheque with welfare/medical equipment after creation"""
        order = super(POSOrder, self).create(vals)
        
        # If order has a cheque and extra_data, link them
        if order.pos_cheque_id and order.extra_data:
            order._link_cheque_to_records()
        
        return order

    def _link_cheque_to_records(self):
        """Link the POS cheque to welfare or medical equipment records"""
        self.ensure_one()
        
        if not self.pos_cheque_id or not self.extra_data:
            return
        
        try:
            extra_data = json.loads(self.extra_data) if isinstance(self.extra_data, str) else self.extra_data
        except (json.JSONDecodeError, TypeError) as e:
            _logger.error(f"Failed to parse extra_data for order {self.name}: {e}")
            return
        
        cheque = self.pos_cheque_id
        
        # Check for medical equipment
        me_data = extra_data.get('medical_equipment', {})
        if me_data:
            medical_equipment_request_no = me_data.get('medical_equipment_request_no')
            if medical_equipment_request_no:
                # Find medical equipment
                medical_equipment = self.env['medical.equipment'].search(
                    [('name', '=', medical_equipment_request_no)], limit=1
                )
                if medical_equipment:
                    # Update cheque with medical equipment reference
                    cheque.write({
                        'medical_equipment_id': medical_equipment.id
                    })
                    
                    # Find or create security deposit and link cheque
                    security_deposit = self.env['medical.security.deposit'].search(
                        [('medical_equipment_id', '=', medical_equipment.id)], limit=1
                    )
                    if security_deposit:
                        security_deposit.write({
                            'pos_cheque_id': cheque.id
                        })
                        cheque.write({
                            'security_deposit_id': security_deposit.id
                        })
                        _logger.info(f"Linked cheque {cheque.name} with security deposit {security_deposit.name}")
        
        # Check for microfinance (if you have microfinance integration)
        mf_data = extra_data.get('microfinance', {})
        if mf_data:
            # Add microfinance linking logic here if needed
            pass

    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        cheque_date = ui_order.get('cheque_date')
        parsed_date = False

        # Fix date parsing (avoid timezone issues)
        if cheque_date:
            try:
                # Handles ISO format like: 2026-03-31T00:00:00.000Z
                parsed_date = fields.Date.to_date(cheque_date[:10])
            except Exception:
                parsed_date = False

        res.update({
            'bank_name': ui_order.get('bank_name') or False,
            'cheque_number': ui_order.get('cheque_number') or False,
            'qr_code': ui_order.get('qr_code') or False,
            'cheque_date': parsed_date,
        })

        # Store extra_data from POS session
        if ui_order.get('extra_data'):
            res['extra_data'] = json.dumps(ui_order['extra_data']) if isinstance(ui_order['extra_data'], dict) else ui_order['extra_data']

        # Create cheque record
        cheque_number = ui_order.get('cheque_number')
        if cheque_number and not ui_order.get('qr_code'):
            cheque = self.env['pos.cheque'].create({
                'bank_name': ui_order.get('bank_name') or False,
                'name': cheque_number,
                'date': parsed_date,
            })
            res['pos_cheque_id'] = cheque.id

        return res
    
    def get_cheque_pos_order(self, shop, offset=0, limit=10):
        orders = self.env['pos.order'].search([
            ('session_id.config_id', '=', shop), 
            ('cheque_state', 'not in', ['clear', 'cancel']), 
            ('cheque_number', '!=', '')
        ], offset=offset, limit=limit)
        
        total_count = self.env['pos.order'].search_count([
            ('session_id.config_id', '=', shop), 
            ('cheque_state', 'not in', ['clear', 'cancel']), 
            ('cheque_number', '!=', '')
        ])
        
        data = []
        
        for order in orders:
            if order.pos_cheque_id:
                status = ""
                reference_name = ""
                reference_type = ""

                if order.cheque_state == "draft":
                    status = "Pending"
                elif order.cheque_state == "bounce":
                    status = "Bounce"
                elif order.cheque_state == "cancel":
                    status = "Cancelled"
                
                # Get reference record name and type
                if order.pos_cheque_id.reference_record_name:
                    reference_name = order.pos_cheque_id.reference_record_name
                    reference_type = order.pos_cheque_id.reference_type

                temp = {
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
                    "status": status,
                    "reference_name": reference_name,  # NEW: Add reference name
                    "reference_type": reference_type,  # NEW: Add reference type
                }

                data.append(temp)
        
        return {
            "orders": data,
            "total_count": total_count  # Send total count for pagination calculation
        }
    
    def get_cheque_pos_order_specific(self, shop, text):
        if text:
            order = self.env['pos.order'].search([
                ('session_id.config_id', '=', shop), 
                ('cheque_number', '=', text)
            ])
            total_count = len(order)
            
            data = []
            
            for i in order:
                reference_name = ""
                reference_type = ""
                
                # Get reference record name if available
                if i.pos_cheque_id and i.pos_cheque_id.reference_record_name:
                    reference_name = i.pos_cheque_id.reference_record_name
                    reference_type = i.pos_cheque_id.reference_type
                
                temp = {
                    "id": i.id,
                    "name": i.name,
                    "date": i.date_order,
                    "ref": i.pos_reference,
                    "customer": i.partner_id.name,
                    "partner_id": i.partner_id.id,
                    "amount": i.amount_total,
                    "cheque_number": i.cheque_number,
                    "bankname": i.bank_name,
                    "status": i.cheque_state,
                    "reference_name": reference_name,  # NEW
                    "reference_type": reference_type,  # NEW
                }
                data.append(temp)

            return {
                "orders": data,
                "total_count": total_count
            }
        
    def redeposite_cheque(self, orderid):
        order = self.env['pos.order'].browse(orderid)
        order.pos_cheque_id.state = 'draft'
    
    def settle_cheque_order(self, orderid):
        order = self.env['pos.order'].browse(orderid)

        if not order:
            return {
                "status": "error",
                "body": "Order does not exist in the system or been delete instead."
            }

        order.pos_cheque_id.state = 'cancel'

        return {
            "status": "success",
            "body": "Cheque Status has been updated successfully."
        }