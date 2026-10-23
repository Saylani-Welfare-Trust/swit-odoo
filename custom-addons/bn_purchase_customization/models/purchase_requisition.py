from odoo import models, fields, api
from odoo.exceptions import ValidationError


PURCHASE_REQUISITION_STATES = [
    ('draft', 'Draft'),
    ('ongoing', 'Ongoing'),
    ('hod_approval', 'HOD Approval'),
    ('mem_approval', 'Member Approval'),
    ('procurement_approval', 'Procurement Manager Approval'),
    ('deferred', 'Deferred / On Hold'),
    ('rfq_sent', 'RFQ Sent'),
    ('vendor_selected', 'Vendor Selected'),
    ('cxo_approved', 'CXO Approved (RFQ)'),
    ('funds_check', 'Funds Availability Check'),
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
    state_blanket_order = fields.Selection(PURCHASE_REQUISITION_STATES, compute='_set_state')


    def _assign_reference_number(self):
        """Give the requisition its number, if it has none yet: the Purchase
        Request sequence for a Purchase Request, otherwise the one
        action_in_progress() takes."""
        for requisition in self.filtered(lambda r: r.name == 'New'):
            code = 'purchase_request_sequence' if requisition.type_id.name == 'Purchase Request' \
                else 'purchase.requisition.blanket.order'
            requisition.name = self.env['ir.sequence'].with_company(requisition.company_id).next_by_code(code)

    def action_in_progress(self):
        self._assign_reference_number()

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