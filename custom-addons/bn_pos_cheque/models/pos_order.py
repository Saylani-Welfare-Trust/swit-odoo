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

        cheque_number = ui_order.get('cheque_number')
        if cheque_number and not ui_order.get('qr_code'):
            cheque_vals = {
                'bank_name': ui_order.get('bank_name') or False,
                'name': cheque_number,
                'date': parsed_date,
            }

            extra_data = ui_order.get('extra_data') or {}
            welfare_data = extra_data.get('welfare')
            me_data = extra_data.get('medical_equipment')

            if welfare_data:
                cheque_vals['source_model'] = 'welfare'
                cheque_vals['source_record_id'] = welfare_data.get('welfare_id')

                line_ids = [l['id'] for l in (welfare_data.get('welfare_line_ids') or []) if l.get('id')]
                recurring_ids = [l['id'] for l in (welfare_data.get('recurring_line_ids') or []) if l.get('id')]
                if line_ids:
                    cheque_vals['welfare_line_ids'] = [(6, 0, line_ids)]
                if recurring_ids:
                    cheque_vals['welfare_recurring_line_ids'] = [(6, 0, recurring_ids)]

            elif me_data:
                cheque_vals['source_model'] = 'medical_equipment'
                equipment_id = me_data.get('equipment_id')
                cheque_vals['source_record_id'] = equipment_id
                if equipment_id:
                    equipment = self.env['medical.equipment'].browse(equipment_id)
                    if equipment.exists():
                        sd_slip = equipment.sd_slip_id
                        if not sd_slip:
                            # fallback: search directly in case sd_slip_id link wasn't set yet
                            sd_slip = self.env['medical.security.deposit'].search(
                                [('medical_equipment_id', '=', equipment_id)], limit=1
                            )
                        if sd_slip:
                            cheque_vals['medical_security_deposit_id'] = sd_slip.id
            cheque = self.env['pos.cheque'].create(cheque_vals)
            res['pos_cheque_id'] = cheque.id

        return res
    
    def get_cheque_pos_order(self, shop, offset=0, limit=10):
        # orders = self.env['pos.order'].search([('session_id.config_id', '=', shop)], offset=offset, limit=limit)
        orders = self.env['pos.order'].search([('session_id.config_id', '=', shop), ('cheque_state', 'not in', ['clear', 'cancel']), ('cheque_number', '!=', '')], offset=offset, limit=limit)
        total_count = self.env['pos.order'].search_count([('session_id.config_id', '=', shop), ('cheque_state', 'not in', ['clear', 'cancel']), ('cheque_number', '!=', '')])
        
        data = []
        
        for order in orders:
            if order.pos_cheque_id:
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
                    "status":i.cheque_state
                }
                data.append(temp)

            return {
                    "orders": data,
                    "total_count": total_count  # Send total count for pagination calculation
                }
        
    def redeposite_cheque(self, orderid):
        order = self.env['pos.order'].browse(orderid)
        
        if order.pos_cheque_id:
            order.pos_cheque_id.state = 'draft'    
    def settle_cheque_order(self, orderid):
        order = self.env['pos.order'].browse(orderid)
        if not order:
            return {"status": "error", "body": "Order does not exist in the system or been delete instead."}

        order.pos_cheque_id.action_cancel()   # <-- was: order.pos_cheque_id.state = 'cancel'

        return {"status": "success", "body": "Cheque Status has been updated successfully."}
        # raise ValidationError(str(order.pos_cheque_id.state))
