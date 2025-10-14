from odoo import models, fields, api




class PosOrder(models.Model):
    _inherit = 'pos.order'



    def action_bounce_ch(self):
        
        self.bounce_cheque(self.id)

    def action_clear_ch(self):
        self.clear_cheque(self.id)

    
    def action_redeposite(self):
        self.redeposite_cheque(self.id)

    
    def action_cancel(self):
        self.cancelled_cheque(self.id)