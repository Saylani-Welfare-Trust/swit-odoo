from odoo import models, fields,api
from odoo.exceptions import UserError


class AnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    balance = fields.Float(
        compute='_compute_debit_credit_balance_balance',
        string='Balance',
    )
    debit = fields.Float(
        compute='_compute_debit_credit_balance_debit',
        string='Debit',
    )
    credit = fields.Float(
        compute='_compute_debit_credit_balance',
        string='Credit',
    )

  

    def _compute_debit_credit_balance(self):
        credit = 0  
        for rec in self:
            if rec.account_ids:
                for acc in rec.account_ids:
                    credit+=acc.credit
                rec.credit = credit
            else:
                rec.credit = 0


    def _compute_debit_credit_balance_balance(self):
        credit = 0  
        for rec in self:
            if rec.account_ids:
                for acc in rec.account_ids:
                    credit+=acc.balance
                rec.balance = credit
            else:
                rec.balance = 0



    def _compute_debit_credit_balance_debit(self):
        credit = 0  
        for rec in self:
            if rec.account_ids:
                for acc in rec.account_ids:
                    credit+=acc.debit
                rec.debit = credit
            else:
                rec.debit = 0


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    
    @api.depends('line_ids.amount')
    def _compute_debit_credit_balance(self):
        super()._compute_debit_credit_balance()
        for rec in self:
            # rec.com = True
            if rec.productline:
                credit,debit=self.get_account(rec.productline)
                
                c = rec.credit + credit
                d= rec.debit+debit
                rec.credit = c
                rec.debit= d
                balance = c-d
                rec.balance = balance+rec.balance 

           
    def get_account(self,productline):
        journal_id = self.env['account.journal'].search([('name','=',"Point of Sale")],limit=1)
        credit = 0
        debit= 0
        if productline:
            account_move = []
            for rec in productline:
                credits_acc,debits_acc = self._get_product_entry_line(rec.product_id.product_entry_line)
                entry = self.env['account.move'].search([('journal_id','=',journal_id.id),('state','=','posted')])
                for move in entry:
                    if move.id not in account_move:
                        account_move.append(move.id)
                        credit += self.get_credit(move,credits_acc)
                        debit += self.get_debit(move,debits_acc)
        return credit,debit                
    
    
    
    
    
    def get_credit(self,move,credits_acc):
        credit = 0
        for rec in credits_acc:
            move_line = self.env['account.move.line'].search([('move_id','=',move.id),('account_id','=',rec.id)])
            for line in move_line:
                if line.credit > 0:
                    credit += line.credit
        return credit

    def get_debit(self,move,debits_acc):
        debit = 0
        for rec in debits_acc:
            move_line = self.env['account.move.line'].search([('move_id','=',move.id),('account_id','=',rec.id)])
            for line in move_line:
                if line.debit > 0:
                    debit += line.debit
        return debit

    def _get_product_entry_line(self,product_entry_line):
        credit_lis = []
        debit_lis = []
        for rec in product_entry_line:
            if rec.for_credit and rec.for_credit not in credit_lis:
                credit_lis.append(rec.for_credit)
            if rec.for_debit and rec.for_debit not in debit_lis:
                debit_lis.append(rec.for_debit)
        return credit_lis,debit_lis