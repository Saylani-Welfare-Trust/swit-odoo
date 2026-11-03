from odoo import models, fields


IBFT_STATUS = [
    ("pending", "Pending"),
    ("success", "Success"),
]


class AccountPayment(models.Model):
    _inherit = "account.payment"

    
    ibft_status = fields.Selection(selection=IBFT_STATUS, string="IBFT Status", default="pending", tracking=True)
    
    
    def action_ibft_success(self):
        
        self.ibft_status = "success"