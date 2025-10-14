from odoo import models, api, fields, _

from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, convert

from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # cheuque_number = fields.Char(string="Cheuqe Number")
    # bank_name = fields.Char(string='Bank Name')


    def get_payment_method(self,order):
        if order:
            for rec in order.payment_ids:
                if rec.payment_method_id:
                    return rec.payment_method_id

    def get_product_payment_id(self,product_id,paymethod):
        line = self.env['product.product.entry'].search([('product_id','=',product_id.id),('online_payment_method_id','=',paymethod.id)],limit=1)
        if line:
            return line
    # def _generate_pos_order_invoice(self):
    #     moves = self.env['account.move']
    #     print("sasasasa")
    #     print("------------------------------------------------------------------------")
    #     print("hunain shaikh")
    #     for order in self:
    #         # Force company for all SUPERUSER_ID action
    #         if order.account_move:
    #             moves += order.account_move
    #             continue

    #         if not order.partner_id:
    #             raise UserError(_('Please provide a partner for the sale.'))

    #         move_vals = order._prepare_invoice_vals()
    #         new_move = order._create_invoice(move_vals)
    #         if new_move:
                
    #             payment_method_id = self.get_payment_method(order)
    #             if payment_method_id:
                    
    #                 for rec in new_move.invoice_line_ids:
    #                     pro_line = self.get_product_payment_id(rec.product_id,payment_method_id)
    #                     if pro_line and  payment_method_id.id == pro_line.online_payment_method_id.id: 
    #                         if pro_line.for_credit:
    #                             rec.write({"account_id" : pro_line.for_credit.id}) 
    #                 for rec in new_move.line_ids:
                        
                        
    #                     pro_line = self.get_product_payment_id(rec.product_id,payment_method_id)
    #                     if pro_line and  payment_method_id.id == pro_line.online_payment_method_id.id: 
                        
    #                         if rec.credit:
    #                             if pro_line.for_credit:
    #                                 rec.write({
    #                                     "credit":pro_line.for_credit.id
    #                                 }) 
    #                         if rec.debit:
    #                             if pro_line.for_debit:
    #                                 rec.write({
    #                                     "debit":pro_line.for_debit.id
    #                                 })
    #         order.write({'account_move': new_move.id, 'state': 'invoiced'})
    #         new_move.sudo().with_company(order.company_id).with_context(skip_invoice_sync=True)._post()

    #         moves += new_move
    #         payment_moves = order._apply_invoice_payments(order.session_id.state == 'closed')

    #         # Send and Print
    #         if self.env.context.get('generate_pdf', True):
    #             template = self.env.ref(new_move._get_mail_template())
    #             new_move.with_context(skip_invoice_sync=True)._generate_pdf_and_send_invoice(template)


    #         if order.session_id.state == 'closed':  # If the session isn't closed this isn't needed.
    #             # If a client requires the invoice later, we need to revers the amount from the closing entry, by making a new entry for that.
    #             order._create_misc_reversal_move(payment_moves)

    #     if not moves:
    #         return {}

    #     return {
    #         'name': _('Customer Invoice'),
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('account.view_move_form').id,
    #         'res_model': 'account.move',
    #         'context': "{'move_type':'out_invoice'}",
    #         'type': 'ir.actions.act_window',
    #         'nodestroy': True,
    #         'target': 'current',
    #         'res_id': moves and moves.ids[0] or False,
    #     }



class PosSession(models.Model):
    _inherit = 'pos.session'

    pos_moves_id = fields.Many2many('account.move',string="Entries")

    def get_payment_method(self,order):
        for rec in order.payment_ids:
            if rec.payment_method_id:
                return rec.payment_method_id


    def create_entries_by_product(self,order_ids):
        entries = []
            
        for order in order_ids:
            order_payment_method = self.get_payment_method(order)
            if order.state != "done" and order.state != "invoiced" and not order.cheque_order:
                order.state = "done"

                for orderline in order.lines:
                    data = {
                        "move_type":"entry",
                        "ref":self.name,
                        "date":order.date_order,
                        "journal_id":9,
                        "company_id":self.env.company.id,
                        "has_reconciled_entries":True
                    }
                    move_id = self.env['account.move'].create(data)
                    product_variant_id = orderline.product_id
                    credit_account_line = self.env['product.product.entry'].search([('product_id','=',product_variant_id.id),('online_payment_method_id','=',order_payment_method.id)],limit=1)
                    temp_list = []
                    data_line_credit = {
                        "move_id":move_id.id,
                        "account_id":credit_account_line.for_credit.id,
                        "name":credit_account_line.for_credit.name,
                        "credit":orderline.price_subtotal_incl,
                        "company_id":self.env.company.id,

                    }
                    temp_list.append(data_line_credit)

                    data_line_debit = {
                        "move_id":move_id.id,
                        "account_id":credit_account_line.for_debit.id,
                        "name":credit_account_line.for_debit.name,
                        "debit":orderline.price_subtotal_incl,
                        "company_id":self.env.company.id,

                    }
                    temp_list.append(data_line_debit)
                    move_id.line_ids.create(temp_list)
                    move_id.action_post()
                    entries.append(move_id.id)
                pp = order.write({
                    "account_move" : move_id.id     

                })
        self.write({"pos_moves_id" : [(6, 0, entries)]})
 
                


    


    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        sudo = self.user_has_groups('point_of_sale.group_pos_user')
        if self.order_ids.filtered(lambda o: o.state != 'cancel') or self.sudo().statement_line_ids:
            self.cash_real_transaction = sum(self.sudo().statement_line_ids.mapped('amount'))
            if self.state == 'closed':
                raise UserError(_('This session is already closed.'))
            self._check_if_no_draft_orders()
            self._check_invoices_are_posted()
            cash_difference_before_statements = self.cash_register_difference
            if self.update_stock_at_closing:
                self._create_picking_at_end_of_session()
                self._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(self.picking_ids.move_ids)
            
            # Skip account.move creation
            data = {'sales': {}}  # Placeholder for compatibility

            self.sudo()._post_statement_difference(cash_difference_before_statements, False)

        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False)

        # Close the session without creating account moves
        print("self.order_ids",self.order_ids)
        if self.order_ids:
            self.create_entries_by_product(self.order_ids)
        self.write({'state': 'closed'})
        return True

    # def _create_account_move(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
    #     """ Create account.move and account.move.line records for this session.

    #     Side-effects include:
    #         - setting self.move_id to the created account.move record
    #         - reconciling cash receivable lines, invoice receivable lines and stock output lines
    #     """
    #     account_move = self.env['account.move'].create({
    #         'journal_id': self.config_id.journal_id.id,
    #         'date': fields.Date.context_today(self),
    #         'ref': self.name,
    #     })
    #     self.write({'move_id': account_move.id})
    #     print("--------------------hunain--------------------------")
        
    #     data = {'bank_payment_method_diffs': bank_payment_method_diffs or {}}
    #     print("data1",data)
    #     data = self._accumulate_amounts(data)
    #     print("data2",data)
    #     data = self._create_non_reconciliable_move_lines(data)
    #     print("data3",data)
    #     data = self._create_bank_payment_moves(data)
    #     print("data4",data)
    #     data = self._create_pay_later_receivable_lines(data)
    #     print("data5",data)
    #     data = self._create_cash_statement_lines_and_cash_move_lines(data)
    #     print("data6",data)
    #     data = self._create_invoice_receivable_lines(data)
    #     print("data7",data)
    #     data = self._create_stock_output_lines(data)
    #     print("data8",data)
    #     if balancing_account and amount_to_balance:
    #         data = self._create_balancing_line(data, balancing_account, amount_to_balance)
    #         print("data9",data)
        
    #     return data
    
    
    
    def _create_non_reconciliable_move_lines(self, data):
        # Create account.move.line records for
        #   - sales
        #   - taxes
        #   - stock expense
        #   - non-cash split receivables (not for automatic reconciliation)
        #   - non-cash combine receivables (not for automatic reconciliation)
        taxes = data.get('taxes')
        sales = data.get('sales')
        stock_expense = data.get('stock_expense')
        rounding_difference = data.get('rounding_difference')
        MoveLine = data.get('MoveLine')
        print("--------------------moveline---------------------")
        print("MoveLine",MoveLine)
        tax_vals = [self._get_tax_vals(key, amounts['amount'], amounts['amount_converted'], amounts['base_amount_converted']) for key, amounts in taxes.items()]
        # Check if all taxes lines have account_id assigned. If not, there are repartition lines of the tax that have no account_id.
        print("tax_vals",tax_vals)
        
        tax_names_no_account = [line['name'] for line in tax_vals if not line['account_id']]
        print("tax_names_no_account",tax_names_no_account)
        
        if tax_names_no_account:
            raise UserError(_(
                'Unable to close and validate the session.\n'
                'Please set corresponding tax account in each repartition line of the following taxes: \n%s',
                ', '.join(tax_names_no_account)
            ))
        rounding_vals = []

        if not float_is_zero(rounding_difference['amount'], precision_rounding=self.currency_id.rounding) or not float_is_zero(rounding_difference['amount_converted'], precision_rounding=self.currency_id.rounding):
            rounding_vals = [self._get_rounding_difference_vals(rounding_difference['amount'], rounding_difference['amount_converted'])]

        MoveLine.create(tax_vals)
        move_line_ids = MoveLine.create([self._get_sale_vals(key, amounts['amount'], amounts['amount_converted']) for key, amounts in sales.items()])
        print("move_line_ids",move_line_ids)
        if move_line_ids:
            self.env['pos.order'].search([('session_id','=',self.id)],limit=1)
            self.order_ids.ids
            payment_method = self.payment_ids[0].payment_method_id.id
            prod = self.lines[0].product_id.id
            acc_id = self.env['product.product.entry'].search([('online_payment_method_id','=',payment_method),('product_id','=',prod)],limit=1)
            if acc_id:
                move_line_ids.write({
                    "account_id":acc_id.for_credit.id
                })
        for key, ml_id in zip(sales.keys(), move_line_ids.ids):
            
            sales[key]['move_line_id'] = ml_id
        MoveLine.create(
            [self._get_stock_expense_vals(key, amounts['amount'], amounts['amount_converted']) for key, amounts in stock_expense.items()]
            + rounding_vals
        )
        
        return data



class AccountMove(models.Model):
    _inherit = 'account.move.line'

    def _check_reconciliation(self):
        for line in self:
            if line.matched_debit_ids or line.matched_credit_ids:
                pass    