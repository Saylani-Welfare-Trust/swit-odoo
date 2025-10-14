from odoo import api, fields, models, _
from odoo.osv import expression
from datetime import datetime
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'


    gender=fields.Selection([('male','Male'),('female','Female')],string='Gender')
    cnic_no=fields.Char(string='CNIC No') 
    date_of_birth=fields.Date(string='Date of Birth') 
    age=fields.Integer(string='Age')
    is_student=fields.Boolean(string="Is Student")
    fee_voucher_count=fields.Integer(compute="_compute_fee_voucher_count", string="Fee Voucher Count")
    
    def action_view_sale_order(self):
        self.ensure_one()
        action=super(ResPartner, self).action_view_sale_order()
        action["domain"].append(("is_fee_voucher", "!=", True))
        return action
    def action_view_fee_vouchers(self):
        self.ensure_one()
        action=super(ResPartner, self).action_view_sale_order()
        action["domain"].append(("is_fee_voucher", "!=", False))
        return action
    
    def _get_sale_order_domain_count(self):
        return [("is_fee_voucher", "!=", True)]
    
    def _compute_fee_voucher_count(self):
        for partner in self:
            partner.fee_voucher_count = self.env['sale.order'].search_count([("partner_id", "=", partner.id),("is_fee_voucher", "=", True)])
    
    def auto_create_fee_voucher(self):
        students=self.env['res.partner'].search([('is_student','=',True)])
        fee_journal=self.env['account.journal'].search([('name','=','Student Fee')],limit=1)
        if not fee_journal:
            raise UserError("Fee Journal not found")
        today = datetime.today()
        first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        product_id=self.env['product.product'].search([('name','=','Student fee')],limit=1)
        if not product_id:
            raise UserError("Fee Product not found")
        
        for student in students:
            fee_voucher=self.env['sale.order'].search([('is_fee_voucher','=',True),('partner_id','=',student.id),('create_date','>',first_day_of_month)])
            if not fee_voucher:
                sale_order=self.env['sale.order'].create({
                    'partner_id':student.id,
                    'is_fee_voucher':True,
                    'order_line':[(0,0,{'product_id':product_id.id})]
                })

                # for line in sale_order.order_line:
                #     raise UserError(line.product_id)

                # raise UserError(str(self.env.company.partner_id.property_account_receivable_id))
                self.env['account.move'].create({
                    'partner_id':student.id,
                    'move_type':'entry',
                    'ref':sale_order.name,
                    'journal_id':fee_journal.id,
                    'line_ids':[
                        (
                            0,0,{
                                # "account_id":line.product_id.property_account_income_id.id,
                                "account_id":line.product_id.product_entry_line[0].for_debit.id if len(line.product_id.product_entry_line) > 0 else None,
                                "debit":line.price_total,
                                "display_type":'product'
                            }
                        ) for line in sale_order.order_line
                    ]+ [(0,0,{"account_id":self.env.company.partner_id.property_account_receivable_id.id,"credit":sale_order.amount_total,"display_type":'product'})]
                    
                }).action_post()
                



