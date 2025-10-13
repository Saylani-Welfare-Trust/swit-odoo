from odoo import models, fields,api
from odoo.exceptions import UserError





class ProductProduct(models.Model):
    _inherit = 'product.product'

    
    for_credit_advance_donation = fields.Many2one('account.account',string='Credit For Advance Donation')

    for_debit_advance_donation = fields.Many2one('account.account',string='Debit for Advance Donation')

