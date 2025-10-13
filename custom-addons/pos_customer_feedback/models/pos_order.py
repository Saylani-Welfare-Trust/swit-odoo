# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author:Anjhana A K(<https://www.cybrosys.com>)
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models,_
from odoo.exceptions import UserError

class PosOrder(models.Model):
    """To add cheuque_number fields and store its value in pos order"""
    _inherit = "pos.order"

    # cheuque_number = fields.Char(string='Feedback', readonly=True,
    #                        help="Please provide your cheuque_number")
    
    
    cheuque_number = fields.Char(string='Cheque', 
                           help="Please provide your cheuque_number")
    
    bank_name = fields.Char(string="Bank Name")
    rating = fields.Char(string='Rating', help="Provide your ratings",
                         )
    comment = fields.Text(string='Comments',  readonly=True,
                          help="Provide the feedbacks in comments")

    cheque_invoice = fields.Many2one('account.move',string='Cheque Invoice')

    cheque_order = fields.Boolean(string="Cheque Order")
    cheque_status = fields.Selection([('pending','Pending'),('clear','Cheque Clear'),('bounce','Cheque Bounce'),('cancelled','Cancelled')])

    bounce_count = fields.Integer(string='Bounce Count')

    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super()._order_fields(ui_order)
        res['bank_name'] = ui_order.get('comment_feedback')
        
        res['cheuque_number'] = ui_order.get('customer_feedback')
        res['comment'] = ui_order.get('comment_feedback')
        if ui_order.get('comment_feedback'):
            res['cheque_status'] = "pending"
            res['cheque_order'] = True
        return res

    def get_cheque_order(self, pos_id, offset=0, limit=10):
            
        order = self.env['pos.order'].search([('session_id.config_id', '=', pos_id), ('cheque_order', '=', True), ('cheque_status', '!=', 'clear')], offset=offset, limit=limit)
        total_count = self.env['pos.order'].search_count([('session_id.config_id', '=', pos_id), ('cheque_order', '=', True),('cheque_status', '!=', 'clear')])  # Get total count of records
        data = []
        for i in order:
            status = ""
            if i.cheque_status == "pending":
                status = "Pending"
            elif i.cheque_status == "bounce":
                status = "Bounce"
            elif i.cheque_status == "cancelled":
                status = "Cancelled"
            

            temp = {
                "id":i.id,
                "name":i.name,
                "date":i.date_order,
                "ref":i.pos_reference,
                "customer":i.partner_id.name,
                "partner_id":i.partner_id.id,
                "amount":i.amount_total,
                "cheuque_number":i.cheuque_number,
                "bankname":i.bank_name,
                "status":status
            }
            data.append(temp)
        return {
                "orders": data,
                "total_count": total_count  # Send total count for pagination calculation
            }

    def get_cheque_order_specific(self, pos_id, text):
        if text:
            order = self.env['pos.order'].search([('session_id.config_id', '=', pos_id), ('cheque_order', '=', True),('cheuque_number','=',text)])
            total_count = self.env['pos.order'].search_count([('session_id.config_id', '=', pos_id), ('cheque_order', '=', True)])  # Get total count of records
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
                    "cheuque_number":i.cheuque_number,
                    "bankname":i.bank_name,
                    "status":i.cheque_status
                }
                data.append(temp)
            return {
                    "orders": data,
                    "total_count": total_count  # Send total count for pagination calculation
                }


    def bounce_cheque(self,orderid):
        entries = []
        move_id = ""
        order = self.env['pos.order'].search([('id','=',orderid)],limit=1)
        if order.bounce_count <=3:
            if order and order.cheque_status == "pending" and order.state != "done":

                for orderline in order.lines:
                    data = {
                        "move_type":"entry",
                        "ref":order.name,
                        "date":order.date_order,
                        "journal_id":9,
                        "company_id":self.env.company.id,
                        "has_reconciled_entries":True
                    }
                    if orderline.product_id.for_credit_bounce and orderline.product_id.for_debit_bounce:
                        move_id = self.env['account.move'].create(data)
                    
                        temp_list = []
                        data_line_credit = {
                            "move_id":move_id.id,
                            "account_id":orderline.product_id.for_credit_bounce.id,
                            "name":orderline.product_id.for_credit_bounce.name,
                            "credit":orderline.price_subtotal_incl,
                            "company_id":self.env.company.id,

                        }
                        temp_list.append(data_line_credit)
                        data_line_debit = {
                            "move_id":move_id.id,
                            "account_id":orderline.product_id.for_debit_bounce.id,
                            "name":orderline.product_id.for_debit_bounce.name,
                            "debit":orderline.price_subtotal_incl,
                            "company_id":self.env.company.id,

                        }
                        temp_list.append(data_line_debit)
                        move_id.line_ids.create(temp_list)
                        move_id.action_post()
                        entries.append(move_id.id)
                        order.state = "done"
                pp = order.write({
                        "account_move" : move_id.id if move_id else False      

                    })
                order.bounce_count = order.bounce_count + 1 
                
                if move_id:
                    order.cheque_status = "bounce"        
        else:
            self.cancelled_cheque(orderid)



    def clear_cheque(self,orderid):
        entries = []
        move_id = ""
        order = self.env['pos.order'].search([('id','=',orderid)],limit=1)
        if order and order.cheque_status == "pending" and order.state != "done":
            for orderline in order.lines:
                data = {
                    "move_type":"entry",
                    "ref":order.name,
                    "date":order.date_order,
                    "journal_id":9,
                    "company_id":self.env.company.id,
                    "has_reconciled_entries":True
                }
                if orderline.product_id.for_credit_clear and orderline.product_id.for_debit_clear:
                    move_id = self.env['account.move'].create(data)
                
                    temp_list = []
                    data_line_credit = {
                        "move_id":move_id.id,
                        "account_id":orderline.product_id.for_credit_clear.id,
                        "name":orderline.product_id.for_credit_clear.name,
                        "credit":orderline.price_subtotal_incl,
                        "company_id":self.env.company.id,

                    }
                    temp_list.append(data_line_credit)
                    data_line_debit = {
                        "move_id":move_id.id,
                        "account_id":orderline.product_id.for_debit_clear.id,
                        "name":orderline.product_id.for_debit_clear.name,
                        "debit":orderline.price_subtotal_incl,
                        "company_id":self.env.company.id,

                    }
                    temp_list.append(data_line_debit)
                    move_id.line_ids.create(temp_list)
                    move_id.action_post()
                    entries.append(move_id.id)
                    order.state = "done"
            pp = order.write({
                    "account_move" : move_id.id if move_id else False      

                })
            if move_id:
                order.cheque_status = "clear"  


    def redeposite_cheque(self,orderid):
        order = self.env['pos.order'].search([('id','=',orderid)],limit=1)
        if order.account_move:
            order.account_move.button_draft()
            order.account_move.button_cancel()
            order.cheque_status = "pending"
            order.state = "paid" 
    
    def cancelled_cheque(self,orderid):
        order = self.env['pos.order'].search([('id','=',orderid)],limit=1)
        if order.account_move:
            order.account_move.button_draft()
            order.account_move.button_cancel()
            order.account_move.unlink()
            order.cheque_status = "cancelled"
            order.state = "paid"
    


    def action_clear_cheque(self,orderid):

        if self.cheuque_number:
            for order in self:
                move_vals = order._prepare_invoice_vals()
                new_move = order._create_invoice(move_vals)
                if new_move:
                    self.cheque_invoice = new_move.id
                if new_move:
                    for rec in new_move.invoice_line_ids:
                        if rec.product_id.for_credit_clear:
                            pro_line = rec.product_id.for_credit_clear
                            if pro_line: 
                                rec.write({"account_id" : pro_line.id}) 
                    
                    for rec in new_move.line_ids:
                        
                        if rec.product_id.for_credit_clear:
                            pro_line = rec.product_id.for_credit_clear
                            if pro_line: 
                            
                                if rec.credit:
                                    rec.write({
                                        "credit":pro_line.id
                                    }) 
                                if rec.debit:
                                    if rec.product_id.for_debit_clear:
                                        rec.write({
                                            "debit":rec.product_id.for_debit_clear.id
                                        })
            if new_move:
                return {
                    'name': _('Customer Invoice'),
                    'view_mode': 'form',
                    'view_id': self.env.ref('account.view_move_form').id,
                    'res_model': 'account.move',
                    'context': "{'move_type':'out_invoice'}",
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'current',
                    'res_id': new_move.id  or False,
                }    
        else:
            raise UserError(str("Cheque Number Empty!"))           
            


    def action_bounce_cheque(self):
        if self.cheuque_number:
            for order in self:
                move_vals = order._prepare_invoice_vals()
                new_move = order._create_invoice(move_vals)
                if new_move:
                    self.cheque_invoice = new_move.id
                if new_move:
                    for rec in new_move.invoice_line_ids:
                        if rec.product_id.for_credit_bounce:
                            pro_line = rec.product_id.for_credit_bounce
                            if pro_line: 
                                rec.write({"account_id" : pro_line.id}) 
                    
                    for rec in new_move.line_ids:
                        
                        if rec.product_id.for_credit_bounce:
                            pro_line = rec.product_id.for_credit_bounce
                            if pro_line: 
                            
                                if rec.credit:
                                    rec.write({
                                        "credit":pro_line.id
                                    }) 
                                if rec.debit:
                                    if rec.product_id.for_debit_bounce:
                                        rec.write({
                                            "debit":rec.product_id.for_debit_bounce.id
                                        })
            if new_move:
                return {
                    'name': _('Customer Invoice'),
                    'view_mode': 'form',
                    'view_id': self.env.ref('account.view_move_form').id,
                    'res_model': 'account.move',
                    'context': "{'move_type':'out_invoice'}",
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'current',
                    'res_id': new_move.id  or False,
                }    
        else:
            raise UserError(str("Cheque Number Empty!"))

    def action_clear(self):
        self.cheque_status = 'clear'
    
    def action_bounce(self):
        self.cheque_status = 'bounce'
        
