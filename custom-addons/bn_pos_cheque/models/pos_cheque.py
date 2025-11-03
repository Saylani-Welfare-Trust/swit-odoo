from odoo import models, fields
from odoo.exceptions import ValidationError


state_selection = [
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('bounce', 'Bounce'),
    ('cancel', 'Cancelled'),
]


class POSCheque(models.Model):
    _name = 'pos.cheque'
    _description = "POS Cheque"


    name = fields.Char('Name')
    
    state = fields.Selection(selection=state_selection, string="State", default='draft')

    bank_name = fields.Char('Bank Name')

    date = fields.Date('Date')

    bounce_count = fields.Integer('Bounce Count')


    def action_show_pos_order(self):
        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'domain': [('pos_cheque_id', '=', self.id)],
            'view_mode': 'tree',
            'target': 'new',
        }

    def action_clear(self):
        self.state = 'clear'
    
    def action_bounce(self):
        # raise ValidationError('Functionality coming soon')
        if self.bounce_count >= 3:
            raise ValidationError('You can not bounce the cheque more then 3 times')

        self.bounce_count += 1
    
    def action_cancel(self):
        self.state = 'cancel'