from odoo import models, fields, api
from odoo.exceptions import ValidationError


PURCHASE_REQUISITION_STATES = [
    ('draft', 'Draft'),
    ('ongoing', 'Ongoing'),
    ('hod_approval', 'HOD Approval'),
    ('mem_approval', 'Member Approval'),
    ('in_progress', 'Confirmed'),
    ('open', 'Bid Selection'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled')
]


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'


    state = fields.Selection(PURCHASE_REQUISITION_STATES,
                              'Status', tracking=True, required=True,
                              copy=False, default='draft')
    state_blanket_order = fields.Selection(PURCHASE_REQUISITION_STATES)


    def action_in_progress(self):
        if self.name == 'New' and self.type_id.name == 'Purchase Request':
            self.name = self.env['ir.sequence'].with_company(self.company_id).next_by_code('purchase_request_sequence')

        super(PurchaseRequisition, self).action_in_progress()

    def action_hod_approval(self):
        self.state = 'hod_approval'

    def action_mem_approval(self):
        self.state = 'mem_approval'
        
class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0