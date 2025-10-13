from odoo import models, fields,api
from odoo.exceptions import UserError
from datetime import date
class AdvanceDonation(models.Model):
    _name = 'advance.donation'

    name= fields.Char(string='Name')
    parnter_id = fields.Many2one('res.partner',string='Customer')
    date = fields.Date(string='From')
    to_date = fields.Date(string="TO")

    line_item = fields.One2many('advance.donation.line', 'advance_donation_id',string='Line Item')
    def check_today_invoice(self,line):
        current_date = date.today()
        for i in line:
            if i.invoice_id:
                for inv in i.invoice_id:
                    if inv.date == current_date:
                        return True
        return False 

    def create_advance_donation_entry(self):
        donation_form = self.env['advance.donation'].search([])    
        current_date = date.today()
        for rec in donation_form:
            if rec.date and rec.to_date:
                diffrence = (rec.to_date - rec.date).days
                diffrence +=1
                if current_date >= rec.date and current_date <= rec.to_date:
                    
                    for line in rec.line_item:
                        invoice_check = self.check_today_invoice(line)
                        if not invoice_check:
                            if len(line.invoice_id.ids) <= diffrence:
                                data = {
                                    "move_type":"entry",
                                    "ref":rec.name,
                                    "date":current_date,
                                    "journal_id":9,
                                    "company_id":self.env.company.id,
                                    "has_reconciled_entries":True
                                }
                                move_id = self.env['account.move'].create(data)
                                temp_list = []
                                data_line_credit = {
                                    "move_id":move_id.id,
                                    "account_id":line.product_id.for_credit_advance_donation.id if line.product_id.for_credit_advance_donation else False,
                                    "name":line.product_id.for_credit_advance_donation.name if line.product_id.for_credit_advance_donation else False,
                                    "credit":line.amount / line.qty,
                                    "company_id":self.env.company.id,

                                }
                                temp_list.append(data_line_credit)

                                data_line_debit = {
                                    "move_id":move_id.id,
                                    "account_id":line.product_id.for_debit_advance_donation.id if line.product_id.for_debit_advance_donation else False,
                                    "name":line.product_id.for_debit_advance_donation.name if line.product_id.for_debit_advance_donation else False,
                                    "debit":line.amount / line.qty,
                                    "company_id":self.env.company.id,

                                }

                                temp_list.append(data_line_debit)
                                move_id.line_ids.create(temp_list)
                                line.invoice_id = [(4, move_id.id)]
                                move_id.action_post()
                                
                            
                            




   

class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.line'

    advance_donation_id = fields.Many2one('advance.donation',string='Advance Donation ID')
    sequence = fields.Integer(string='sequence')
    display_type = fields.Char(string="Display")
    name = fields.Char(string="name")
    product_id = fields.Many2one('product.product',string='Product')
    bank_name = fields.Char(string='Bank Name')
    cheque_num = fields.Char(string='Cheque Number')
    date = fields.Date(string='Date')
    
    company_id = fields.Many2one('res.company', store=True, copy=False,
    string="Company",
    default=lambda self: self.env.user.company_id.id)

    currency_id = fields.Many2one('res.currency', string="Currency",
        related='company_id.currency_id',
        default=lambda
        self: self.env.user.company_id.currency_id.id)
    qty = fields.Integer(string='QTY')
    amount = fields.Monetary(string="Amount") 

    credit_account = fields.Many2one('account.account',string='Credit Account')

    debit_account = fields.Many2one('account.account',string='Debit Account')


    invoice_id = fields.Many2many('account.move',string='Invoice')
    posted_entry = fields.Boolean(string='Posted Entry',default=True)
    @api.onchange('product_id')
    def product_id_onchange(self):
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name

    def action_create_invoice(self):
        
        
        if not (self.credit_account and self.debit_account):
            raise UserError("Please Select Credit Debit Accounts")
    
        if not self.advance_donation_id.parnter_id:
            raise UserError("Select Customer!")

        if self.invoice_id:
            raise UserError("Invoice Has Already Generated")



        account_move = self.env['account.move']
        account_move_line = self.env['account.move.line']
        data = {
            "partner_id":self.advance_donation_id.parnter_id.id,
            "invoice_date":self.date,
            "move_type":"out_invoice",
            
        }

        move = account_move.create(data)


        line_date = {
            "move_id":move.id,
            "product_id":self.product_id.id,
            "account_id":self.credit_account.id,
            "quantity":self.qty,
            "price_unit":self.amount,
            "product_uom_id":self.product_id.uom_id.id,
        }
        
        account_move_line.create(line_date)
        
       
        if self.posted_entry:
            move.action_post()
        self.invoice_id = move.id 
