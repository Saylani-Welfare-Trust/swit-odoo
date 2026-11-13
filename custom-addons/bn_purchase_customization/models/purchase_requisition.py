from odoo import models, fields, api
from odoo.exceptions import ValidationError


# The purchase request steps, added among the purchase_requisition statuses
# (draft, ongoing, in_progress, open, done, cancel) in this order.
PURCHASE_REQUISITION_STATES_ADD = [
    ('draft',),
    ('confirm', 'Confirm'),
    ('ongoing',),
    ('procurement_approval', 'Procurement Manager Approval'),
    ('deferred', 'Deferred / On Hold'),
    ('rfq_sent', 'RFQ Sent'),
    ('vendor_selected', 'Vendor Selected'),
    ('cxo_approved', 'CXO Approved (RFQ)'),
    ('funds_check', 'Funds Availability Check'),
    ('in_progress',),
]
_ADDED_STATES_ONDELETE = {key[0]: 'set default' for key in PURCHASE_REQUISITION_STATES_ADD if len(key) == 2}


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'


    state = fields.Selection(selection_add=PURCHASE_REQUISITION_STATES_ADD, ondelete=_ADDED_STATES_ONDELETE)
    state_blanket_order = fields.Selection(selection_add=PURCHASE_REQUISITION_STATES_ADD)


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

    def action_confirm(self):
        if not self.env.su and not self.env.user.has_group('bn_purchase_customization.purchase_request_confirm_group'):
            raise ValidationError('You are not allowed to confirm a Purchase Request.')
        for requisition in self:
            if requisition.state != 'draft':
                raise ValidationError('Only a Draft request can be confirmed.')
        self.write({'state': 'confirm'})

    @api.model
    def _move_from_removed_states(self):
        """Requests left in a state that no longer exists (HOD Approval, Member
        Approval) are moved back to Confirm, the step they came from. Run at
        module update."""
        # sudo: run at module update.
        self.sudo().search([('state', 'in', ('hod_approval', 'mem_approval'))]).with_context(
            tracking_disable=True).write({'state': 'confirm'})
        
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