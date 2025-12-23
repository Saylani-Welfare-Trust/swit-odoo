from odoo import models


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'


    def action_in_progress(self):
        if self.name == 'New' and self.type_id.name == 'Purchase Request':
            self.name = self.env['ir.sequence'].with_company(self.company_id).next_by_code('purchase_requrest_sequence')

        super(PurchaseRequisition, self).action_in_progress()