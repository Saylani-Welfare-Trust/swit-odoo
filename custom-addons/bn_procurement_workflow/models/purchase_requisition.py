# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


APPROVAL_RESULTS = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    requesting_department_id = fields.Many2one(
        related='material_request_id.department_id',
        string='Requesting Department', store=True, readonly=True)

    # Procurement Manager review / defer
    procurement_manager_id = fields.Many2one('res.users', string='Procurement Manager', readonly=True, copy=False)
    procurement_review_date = fields.Datetime(readonly=True, copy=False)
    defer_reason = fields.Text(string='Deferral Reason')

    # Technical evaluation (requesting department's HOD/CXO)
    technical_evaluation_result = fields.Selection(
        APPROVAL_RESULTS, string='Technical Evaluation', default='pending', copy=False, tracking=True)
    technical_evaluation_remarks = fields.Text(string='Technical Evaluation Remarks')
    technical_evaluator_id = fields.Many2one('res.users', readonly=True, copy=False)
    technical_evaluation_date = fields.Datetime(readonly=True, copy=False)

    # HOD Procurement commercial approval
    hod_procurement_result = fields.Selection(
        APPROVAL_RESULTS, string='HOD Procurement Approval', default='pending', copy=False, tracking=True)
    hod_procurement_remarks = fields.Text(string='HOD Procurement Remarks')
    hod_procurement_id = fields.Many2one('res.users', readonly=True, copy=False)
    hod_procurement_date = fields.Datetime(readonly=True, copy=False)

    # Funds availability gate
    funds_available = fields.Boolean(string='Funds Available', copy=False, tracking=True)
    funds_transfer_remarks = fields.Text(string='CFO / Shariah Fund Transfer Remarks')
    funds_gate_approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    funds_gate_date = fields.Datetime(readonly=True, copy=False)

    # Winning RFQ tracked through the gate chain
    selected_rfq_id = fields.Many2one('purchase.order', string='Selected RFQ / Winning Quote',
                                       readonly=True, copy=False)

    def action_procurement_approve(self):
        """Procurement Manager reviews and approves the draft PR directly - no HOD/Member
        approval step in this workflow. Moves the PR into its own 'Procurement Manager
        Approval' state, which unlocks RFQ creation."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_('This request is not in Draft state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can approve this request.'))
        if not self.material_request_id:
            raise ValidationError(
                _('This Purchase Requisition has no source Material Request, so there is no '
                  'requesting department to run Technical Evaluation against. It cannot enter '
                  'the Procurement workflow.'))
        self.write({
            'procurement_manager_id': self.env.user.id,
            'procurement_review_date': fields.Datetime.now(),
            'state': 'procurement_approval',
        })
        self.message_post(body=_('Approved by Procurement Manager - ready for RFQs to be sent to vendors.'))

    def action_open_defer_wizard(self):
        """Open the small popup collecting the mandatory deferral reason."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_('This request is not in Draft state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can defer this request.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Defer Purchase Requisition'),
            'res_model': 'procurement.defer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_requisition_id': self.id},
        }

    def action_procurement_defer(self, reason):
        """Procurement Manager defers the PR instead of approving it."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_('This request is not in Draft state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can defer this request.'))
        if not reason:
            raise ValidationError(_('Please provide a deferral reason.'))
        self.write({'state': 'deferred', 'defer_reason': reason})
        self.message_post(body=_('Purchase Requisition deferred by Procurement Manager.\nReason: %s') % reason)

    def action_procurement_resume(self):
        """Resume a deferred PR back to Draft for Procurement Manager review."""
        self.ensure_one()
        if self.state != 'deferred':
            raise ValidationError(_('This request is not Deferred.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can resume this request.'))
        self.state = 'draft'

    def action_mark_rfq_sent(self):
        """Called once RFQs have been created for this requisition."""
        self.ensure_one()
        if self.state != 'procurement_approval':
            raise ValidationError(_('This request is not in Procurement Manager Approval state.'))
        if not self.procurement_manager_id:
            raise ValidationError(_('This request must be approved by the Procurement Manager before RFQs can be sent.'))
        self.state = 'rfq_sent'

    def action_send_to_technical_evaluation(self, winning_po):
        """Called by the RFQ price wizard once a winning quote has been selected."""
        self.ensure_one()
        if self.state != 'rfq_sent':
            raise ValidationError(_('This request is not in RFQ Sent state.'))
        self.write({
            'selected_rfq_id': winning_po.id,
            'technical_evaluation_result': 'pending',
            'hod_procurement_result': 'pending',
            'state': 'technical_evaluation',
        })
        self.message_post(body=_('Quote from %s selected and sent for Technical Evaluation.') % winning_po.partner_id.display_name)

    def action_technical_evaluate_approve(self):
        self.ensure_one()
        self._action_technical_evaluate(True, self.technical_evaluation_remarks)

    def action_technical_evaluate_reject(self):
        self.ensure_one()
        self._action_technical_evaluate(False, self.technical_evaluation_remarks)

    def _action_technical_evaluate(self, approved, remarks):
        """Technical Evaluation by the requesting department's HOD/CXO."""
        self.ensure_one()
        if self.state != 'technical_evaluation':
            raise ValidationError(_('This request is not in Technical Evaluation state.'))
        manager = self.requesting_department_id.manager_id
        if not manager or manager.user_id.id != self.env.user.id:
            raise ValidationError(_('Only the requesting department\'s HOD can perform Technical Evaluation.'))
        if not remarks:
            raise ValidationError(_('Technical Evaluation remarks are required.'))
        self.write({
            'technical_evaluation_result': 'approved' if approved else 'rejected',
            'technical_evaluation_remarks': remarks,
            'technical_evaluator_id': self.env.user.id,
            'technical_evaluation_date': fields.Datetime.now(),
        })
        if approved:
            self.state = 'hod_procurement_approval'
            self.message_post(body=_('Technical Evaluation approved.\nRemarks: %s') % remarks)
        else:
            self.state = 'rfq_sent'
            self.message_post(body=_('Technical Evaluation rejected — returned for re-quoting.\nRemarks: %s') % remarks)

    def action_hod_procurement_approve_btn(self):
        self.ensure_one()
        self._action_hod_procurement_approve(True, self.hod_procurement_remarks)

    def action_hod_procurement_reject_btn(self):
        self.ensure_one()
        self._action_hod_procurement_approve(False, self.hod_procurement_remarks)

    def _action_hod_procurement_approve(self, approved, remarks):
        """HOD (Procurement) approval of the vendor selection."""
        self.ensure_one()
        if self.state != 'hod_procurement_approval':
            raise ValidationError(_('This request is not in HOD Procurement Approval state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_hod_procurement'):
            raise ValidationError(_('Only HOD Procurement can approve the vendor selection.'))
        if not remarks:
            raise ValidationError(_('HOD Procurement remarks are required.'))
        self.write({
            'hod_procurement_result': 'approved' if approved else 'rejected',
            'hod_procurement_remarks': remarks,
            'hod_procurement_id': self.env.user.id,
            'hod_procurement_date': fields.Datetime.now(),
        })
        if approved:
            self.state = 'funds_check'
            self.message_post(body=_('HOD Procurement approved the vendor selection.\nRemarks: %s') % remarks)
        else:
            self.state = 'rfq_sent'
            self.message_post(body=_('HOD Procurement rejected the vendor selection — returned for re-quoting.\nRemarks: %s') % remarks)

    def action_funds_available(self):
        """Decide whether funds are available for the selected quote."""
        self.ensure_one()
        if self.state != 'funds_check':
            raise ValidationError(_('This request is not in Funds Availability Check state.'))
        self.write({
            'funds_available': True,
            'funds_gate_approver_id': self.env.user.id,
            'funds_gate_date': fields.Datetime.now(),
        })
        self.message_post(body=_('Funds confirmed available.'))
        self._release_po()

    def action_funds_unavailable(self):
        self.ensure_one()
        if self.state != 'funds_check':
            raise ValidationError(_('This request is not in Funds Availability Check state.'))
        self.write({'funds_available': False, 'funds_transfer_remarks': self.funds_transfer_remarks})
        self.message_post(body=_('Funds not available — awaiting CFO / Shariah Dept fund transfer.'))

    def action_cfo_shariah_transfer_confirm(self):
        """CFO or Shariah Dept confirms funds have been transferred."""
        self.ensure_one()
        remarks = self.funds_transfer_remarks
        if self.state != 'funds_check':
            raise ValidationError(_('This request is not in Funds Availability Check state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_cfo_shariah'):
            raise ValidationError(_('Only CFO / Shariah Dept can confirm a fund transfer.'))
        if not remarks:
            raise ValidationError(_('Fund transfer remarks are required.'))
        self.write({
            'funds_available': True,
            'funds_transfer_remarks': remarks,
            'funds_gate_approver_id': self.env.user.id,
            'funds_gate_date': fields.Datetime.now(),
        })
        self.message_post(body=_('CFO / Shariah Dept confirmed fund transfer.\nRemarks: %s') % remarks)
        self._release_po()

    def action_view_selected_rfq(self):
        self.ensure_one()
        if not self.selected_rfq_id:
            raise ValidationError(_('No selected RFQ found.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Selected RFQ'),
            'res_model': 'purchase.order',
            'res_id': self.selected_rfq_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _release_po(self):
        """Confirm the winning RFQ and mark the requisition as Confirmed.

        The Technical Evaluation (by the requesting department's HOD/CXO) and
        HOD Procurement approval already recorded on this requisition satisfy
        the same CXO + HOD approval that purchase.order.button_confirm() now
        requires on every purchase order, so mark the winning RFQ approved
        here rather than asking the same people to approve it a second time
        on the PO itself.
        """
        self.ensure_one()
        if not self.selected_rfq_id:
            raise ValidationError(_('No selected RFQ to release.'))
        self.selected_rfq_id.write({
            'cxo_approved': True,
            'cxo_approved_by': self.technical_evaluator_id.id,
            'cxo_approved_date': self.technical_evaluation_date,
            'hod_approved': True,
            'hod_approved_by': self.hod_procurement_id.id,
            'hod_approved_date': self.hod_procurement_date,
        })
        self.selected_rfq_id.button_confirm()
        self.action_in_progress()
