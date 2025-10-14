from odoo import fields, models
from odoo.exceptions import UserError
class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    pos_register_order_id = fields.Many2one('pos.registered.order', string="POS Order")
    donation_journal_entry_id = fields.Many2one('account.move',string="Journal Entry")
    
    
    def button_validate(self):
        for rec in self:
            if rec.pos_register_order_id and rec.donation_journal_entry_id:
                rec.donation_journal_entry_id.action_post()
            
        picking = super().button_validate()
        return picking
