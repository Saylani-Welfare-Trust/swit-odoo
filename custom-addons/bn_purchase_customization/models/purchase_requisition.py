from odoo import models
from odoo.exceptions import ValidationError


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'


    def action_in_progress(self):
        if self.name == 'New' and self.type_id.name == 'Purchase Request':
            self.name = self.env['ir.sequence'].with_company(self.company_id).next_by_code('purchase_request_sequence')
            
            # raise ValidationError(str(self.name))

        super(PurchaseRequisition, self).action_in_progress()