from odoo import models, fields, Command

class AccountMove(models.Model):
    _inherit = "account.move"
    
    pos_register_order_id = fields.Many2one('pos.registered.order', string="POS Order")
    journal_entry = fields.Many2one('account.move',string="Journal Entry")