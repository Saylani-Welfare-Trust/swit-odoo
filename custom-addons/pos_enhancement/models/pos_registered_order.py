from odoo import _,fields, models, api
from odoo.exceptions import UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import random
import string

class PosRegisteredOrder(models.Model):
    _name="pos.registered.order"

    name=fields.Char(string="Name")
    partner_id=fields.Many2one('res.partner',string="Donee")
    registrar=fields.Many2one('res.users',string="Registrar")
    state=fields.Selection([('active','Acive'),('expire','Expired')],default="active",string="State")
    barcode=fields.Char(string="Barcode",readonly=True)
    order_lines=fields.One2many('pos.registered.order.line','order_id',string="Order Lines")
    validation_lines=fields.One2many('order.validate.line','order_id',string="Validation Lines")
    description=fields.Text(string="Description")
    pos_reference=fields.Char(string="POS Reference")
    disbursement_type=fields.Selection([('in_kind','In Kind Support'),('cash','Cash Support')],string='Disbursement Type')
    order_type=fields.Selection([('one_time','One Time'),('recurring','Recurring')],default="one_time",string="Order Type")
    analytic_account_ids=fields.Many2many('account.analytic.account',string="Analytic Accounts")
    total_amount=fields.Float(string="Total Amount",compute="_compute_total_amount")
    is_payment_validated=fields.Boolean(string="Is Payment Validated",compute="_compute_is_payment_validated")
    reprint_support=fields.Selection([
        ('daily','Daily'),
        ('monthly','Monthly'),
        ('yearly','Yearly'),
        ('no_limit','No Limit')
    ],default="no_limit",string="Reprint Support")
    amount_total=fields.Float(string="Amount Total")
    in_kind_transaction_type=fields.Selection([
        ('ration','Ration Support'),
        ('ramzan','Ramzan Support'),
        ('meal','Meal Distribution'),
        ('medicines','Medicines - General'),
        ('medicines_cancer','Medicines - Cancer Support'),
        ('assisted_devices','Artificial Limbs & Assisted Devices'),
        ('madaris','Madaris Support'),
        ('masjid','Masajid Support'),
        ('wedding','Wedding Support Program')],
        string='Transaction Type')
    
    cash_transaction_type=fields.Selection([
        ('scholarship','Scholarship'),
        ('kifalat','Kifalat Program'),
        ('rozgar','Rozgar Schemes')],
        string='Transaction Type')
    
    transaction_type=fields.Selection([
        ('ration','Ration Support'),
        ('ramzan','Ramzan Support'),
        ('meal','Meal Distribution'),
        ('medicines','Medicines - General'),
        ('medicines_cancer','Medicines - Cancer Support'),
        ('assisted_devices','Artificial Limbs & Assisted Devices'),
        ('madaris','Madaris Support'),
        ('masjid','Masajid Support'),
        ('wedding','Wedding Support Program'),
        ('scholarship','Scholarship'),
        ('kifalat','Kifalat Program'),
        ('rozgar','rozgar Schemes')],
        string='Transaction Type',compute="_compute_transaction_type", store=True)
    
    pos_session_id=fields.Many2one('pos.session',string="POS Session")
    
    @api.depends('order_lines')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.order_lines.filtered(lambda l: l.product_id.is_subsidised).mapped('amount'))
    
    @api.depends('disbursement_type','in_kind_transaction_type','cash_transaction_type')
    def _compute_transaction_type(self):
        for rec in self:
            if rec.disbursement_type == 'in_kind':
                rec.transaction_type = rec.in_kind_transaction_type if rec.in_kind_transaction_type else ""
            elif rec.disbursement_type == 'cash':
                rec.transaction_type = rec.cash_transaction_type if rec.cash_transaction_type else ""
            else:
                rec.transaction_type = ""
    
    def active_deactive(self):
        for rec in self:
            rec.state = 'expire'
            
    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('registered.order')
            vals['barcode'] = self._generate_random_barcode()
        # raise UserError(str(vals_list))
        return super(PosRegisteredOrder, self).create(vals_list)
    
    @api.model
    def create_from_ui(self, orders, draft=False):
        
        order_ids = []
        for order in orders:
            order=order['data']
            # raise UserError(str(order['statement_ids']))
            lines=[line[2] for line in order['lines']]
            # raise UserError(str(lines))
            
            values={
                'pos_reference':order['name'],
                'partner_id':order['partner_id'],
                'registrar':order['user_id'],
                'order_type':order['order_type'],
                'disbursement_type':order['disbursement_type'],
                'in_kind_transaction_type':order['in_kind_transaction_type'] if order['disbursement_type'] == 'in_kind' else False,
                'cash_transaction_type':order['cash_transaction_type'] if order['disbursement_type'] == 'cash' else False,
                'amount_total':order['amount_total'],
                'analytic_account_ids':[(4,analytic['id']) for analytic in order['analytic_account_ids']],
                'reprint_support':order['reprint_support'],
                'description':order['description'],
                'pos_session_id':order['pos_session_id'],
                'order_lines': [(0, 0, {
                    'product_id': line['product_id'] ,
                    'price_unit': line['price_unit'],
                    'qty': line['qty'],
                    'price_subtotal': line['price_subtotal'],
                    'name': line['full_product_name']
                    }) for line in lines],
                'validation_lines':[(0,0,{
                    'print_date':fields.Datetime.now(),
                    'pos_session_id':order['pos_session_id'],
                    'payment_ids':order['statement_ids']
                    })]
            }
            # raise UserError(str(values))
            order_ids.append(self.env['pos.registered.order'].sudo().create(values))
            # raise UserError(str(list(map(lambda order: order.validation_lines.mapped(lambda line: line.payment_ids),order_ids))))
            
            new_orders=map(lambda order: {
                'id': order.id,
                'pos_reference': order.pos_reference,
                'barcode': order.barcode,
                # 'amount_total': order.amount_total
            },order_ids)
        
        
        return list(new_orders)
    
    def _generate_random_barcode(self):
        barcode = ''.join(random.choices(string.digits, k=12))  # Generate a 12-digit number
        return barcode
    
    def get_next_reprint_date(self):
        self.ensure_one()
        most_recent=self._get_most_recent_validation_line()
        if self.reprint_support =='daily':
            return most_recent.print_date + timedelta(days=1)
        if self.reprint_support == 'weekly':
            return most_recent.print_date + timedelta(weeks=1)
        if self.reprint_support == 'monthly':
            return most_recent.print_date + relativedelta(months=1)
        if self.reprint_support == 'no_limit':
            return fields.Datetime.now()
    
    
    
    def export_for_printing(self,payment_ids=False):
        # raise UserError("olll "+str(amount))
        self.ensure_one()
        
        most_recent=self._get_most_recent_validation_line()
        next_date=self.get_next_reprint_date()
        
        if next_date > fields.Datetime.now() and most_recent.validation_date:
            return {"error": "Order already validated"}
            
        if next_date <= fields.Datetime.now() and most_recent.validation_date:
            # if self.amount_total:
            #     # [[0, 0, {'name': '2024-12-24 19:57:08', 'payment_method_id': 1, 'amount': 1.1500000000000001, 'payment_status': '', 'ticket': '', 'card_type': '', 'cardholder_name': '', 'transaction_id': ''}]]
            #     pass
            self.validation_lines = [(0,0,{'print_date':fields.Datetime.now(),'pos_session_id':self.pos_session_id.id,'payment_ids':payment_ids})]  
        elif next_date <= fields.Datetime.now() and not most_recent.validation_date:
            most_recent.write({
                'print_date':fields.Datetime.now()
            }) 
    
            
        return {
            "orderlines": [
                {
                    "productName": line.product_id.name,
                    "price": str(line.price_unit),
                    "price_subtotal":line.price_subtotal,
                    "qty": str(line.qty),
                    "unit": "Units",
                    "unitPrice": str(line.price_unit),
                    "attributes": []
                } for line in self.order_lines],
            "paymentlines": [],
            "amount_total": self.amount_total,
            "rounding_applied": 0,
            "tax_details": [],
            "change": 0,
            "name": self.pos_reference,
            "cashier": self.registrar.name,
            "date": self.create_date,
            "barcode": self.barcode,
            "description": self.description
        }
    
    def _get_most_recent_validation_line(self):
        if self.validation_lines:
            sorted_lines=self.validation_lines.sorted(key=lambda line: line.print_date,reverse=True)
            most_recent=sorted_lines[0]
            return most_recent
        else:
            return False
      
    def is_applicable(self):
        self.ensure_one()
        most_recent=self._get_most_recent_validation_line()
        # raise UserError(str(most_recent.read()))
        if most_recent:
            if most_recent.validation_date:
                return False
            else:
                return True
        else:
            return False

    
    def order_validate(self,new_reference,account_move):
        self.ensure_one()
        most_recent=self._get_most_recent_validation_line()
        if most_recent.validation_date:
            raise UserError(_('Order already validated'))
        else:
            most_recent.write({
                'validation_date':fields.Datetime.now(),
                'validated_by':self.env.user.id,
                'reference_no':new_reference,
                'journal_entry':account_move.id
            })
    
    
    @api.model
    def _get_invoice_lines_values(self, line):
        return {
            'product_id': line.product_id.id,
            'quantity': line.qty,
            'price_unit': line.price_unit,
            'name': line.product_id.name
        }
    
    def _prepare_invoice_lines(self):
        self.ensure_one()
        invoice_lines = []
        for line in self.order_lines:
            invoice_lines_values = self._get_invoice_lines_values(line)
            invoice_lines.append((0, None, invoice_lines_values))

        return invoice_lines
    
    def _compute_is_payment_validated(self):
        for rec in self:
            most_recent=rec._get_most_recent_validation_line()
            if most_recent.payment_ids and not most_recent.validation_date:
                rec.is_payment_validated=True
            else:
                rec.is_payment_validated=False
            
            
        

