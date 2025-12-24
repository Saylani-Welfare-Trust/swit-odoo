from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['bank_name'] = ui_order.get('bank_name') or False
        res['cheque_number'] = ui_order.get('cheque_number') or False
        res['qr_code'] = ui_order.get('qr_code') or False
        res['cheque_date'] = ui_order.get('cheque_date') or False

        # Create pos.cheque record if cheque_number is provided and not a QR code payment
        cheque_number = ui_order.get('cheque_number')
        if cheque_number and not ui_order.get('qr_code'):
            cheque = self.env['pos.cheque'].create({
                'bank_name': ui_order.get('bank_name') or False,
                'name': cheque_number,
                'date': ui_order.get('cheque_date') or False,
            })
            res['pos_cheque_id'] = cheque.id
        
        return res
    
    def get_cheque_pos_order(self, shop, offset=0, limit=10):
        # orders = self.env['pos.order'].search([('session_id.config_id', '=', shop)], offset=offset, limit=limit)
        orders = self.env['pos.order'].search([('session_id.config_id', '=', shop), ('cheque_state', 'not in', ['clear', 'cancel']), ('cheque_number', '!=', '')], offset=offset, limit=limit)
        total_count = self.env['pos.order'].search_count([('session_id.config_id', '=', shop), ('cheque_state', 'not in', ['clear', 'cancel']), ('cheque_number', '!=', '')])
        
        data = []
        
        for order in orders:
            status = ""

            if order.cheque_state == "draft":
                status = "Pending"
            elif order.cheque_state == "bounce":
                status = "Bounce"
            elif order.cheque_state == "cancel":
                status = "Cancelled"
            

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
                "status":status
            }

            data.append(temp)
        
        return {
            "orders": data,
            "total_count": total_count  # Send total count for pagination calculation
        }
    
    def get_cheque_pos_order_specific(self, shop, text):
        if text:
            order = self.env['pos.order'].search([('session_id.config_id', '=', shop), ('cheque_number', '=', text)])
            total_count = len(order)
            
            data = []
            
            for i in order:
                temp = {
                    "id":i.id,
                    "name":i.name,
                    "date":i.date_order,
                    "ref":i.pos_reference,
                    "customer":i.partner_id.name,
                    "partner_id":i.partner_id.id,
                    "amount":i.amount_total,
                    "cheque_number":i.cheque_number,
                    "bankname":i.bank_name,
                    "status":i.cheque_status
                }
                data.append(temp)

            return {
                    "orders": data,
                    "total_count": total_count  # Send total count for pagination calculation
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


        # raise ValidationError(str(order))
        # raise ValidationError(str(order.pos_cheque_id))
        
        order.pos_cheque_id.state = 'cancel'

        return {
            "status": "success",
            "body": "Cheque Status has been updated successfully."
        }
        # raise ValidationError(str(order.pos_cheque_id.state))
