from odoo import models, fields,api
from odoo.exceptions import UserError

class DonationCredit(models.Model):
    _name = 'donation.credit'

    name= fields.Char(string='Name')
    parnter_id = fields.Many2one('res.partner',string='Customer')
    date = fields.Date(string='Date')

    line_item = fields.One2many('donation.credit.line', 'advance_donation_id',string='Line Item')

   

class DonationCreditLine(models.Model):
    _name = 'donation.credit.line'

    advance_donation_id = fields.Many2one('donation.credit',string='Advance Donation ID')
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


    invoice_id = fields.Many2one('account.move',string='Invoice')
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
