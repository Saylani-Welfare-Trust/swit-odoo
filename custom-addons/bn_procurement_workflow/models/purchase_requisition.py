# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    requesting_department_id = fields.Many2one(
        related='material_request_id.department_id',
        string='Requesting Department', store=True, readonly=True)

    # Procurement Manager review / defer
    procurement_manager_id = fields.Many2one('res.users', string='Procurement Manager', readonly=True, copy=False)
    procurement_review_date = fields.Datetime(readonly=True, copy=False)
    defer_reason = fields.Text(string='Deferral Reason')

    # Funds availability gate
    funds_available = fields.Boolean(string='Funds Available', copy=False, tracking=True)
    funds_transfer_remarks = fields.Text(string='CFO / Shariah Fund Transfer Remarks')
    funds_gate_approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    funds_gate_date = fields.Datetime(readonly=True, copy=False)

    # Winning RFQ tracked through the gate chain. CXO and HOD approval happen
    # only once, directly on this RFQ (purchase.order.action_cxo_approve_po /
    # action_hod_approve_po from bn_purchase_customization) - this
    # requisition's own state advances automatically as a reflection of that
    # RFQ's approval progress, see models/purchase_order.py in this module.
    selected_rfq_id = fields.Many2one('purchase.order', string='Selected RFQ / Winning Quote',
                                       readonly=True, copy=False)
    # Deliberately NOT written onto the native vendor_id field: doing so would
    # flip action_in_progress() into its blanket-order branch, which requires
    # every purchase.requisition.line to already have a price_unit > 0 - those
    # lines never carry a price in this Material Request flow (only the RFQ's
    # own order lines do), so that would break _release_po() outright.
    selected_vendor_id = fields.Many2one(
        related='selected_rfq_id.partner_id', string='Selected Vendor', store=True)
    selected_rfq_cxo_approved = fields.Boolean(
        related='selected_rfq_id.cxo_approved', string='CXO Approved (on RFQ)')
    selected_rfq_cxo_approved_by = fields.Many2one(
        related='selected_rfq_id.cxo_approved_by', string='CXO Approved By')
    selected_rfq_hod_approved = fields.Boolean(
        related='selected_rfq_id.hod_approved', string='HOD Approved (on RFQ)')
    selected_rfq_hod_approved_by = fields.Many2one(
        related='selected_rfq_id.hod_approved_by', string='HOD Approved By')

    # Automatic Shariah Law balance check for the Funds Availability gate
    funds_shariah_balance = fields.Monetary(
        string='Shariah Law Closing Balance', currency_field='currency_id',
        compute='_compute_shariah_funds_check')
    funds_shariah_ok = fields.Boolean(
        string='Shariah Balance Sufficient', compute='_compute_shariah_funds_check')

    @api.depends('selected_rfq_id', 'selected_rfq_id.order_line.price_subtotal', 'state')
    def _compute_shariah_funds_check(self):
        for requisition in self:
            is_ok, balance, _accounts = requisition._get_shariah_funds_check()
            requisition.funds_shariah_ok = is_ok
            requisition.funds_shariah_balance = balance

    def _get_shariah_funds_check(self):
        """Match the winning RFQ's lines to their Shariah Law segment (analytic
        account) and check whether each segment's closing balance covers what
        this purchase is about to commit - the same matching bn_shariah_law
        already does on purchase.order.button_confirm(), surfaced here so the
        Funds Availability gate reflects it instead of being a blind manual
        approval."""
        self.ensure_one()
        shariah_law = self.env['shariah.law']
        rfq = self.selected_rfq_id
        insufficient_accounts = self.env['account.analytic.account']
        lowest_balance = 0.0
        if not rfq:
            return True, lowest_balance, insufficient_accounts
        balances = []
        for line in rfq.order_line:
            if not line.product_id:
                continue
            analytic = self.env['account.analytic.account'].search(
                [('product_ids', 'in', [line.product_id.id])], limit=1)
            if not analytic:
                continue
            balance = shariah_law.get_closing_balance(analytic.id)
            balances.append(balance)
            if line.price_subtotal > balance:
                insufficient_accounts |= analytic
        if balances:
            lowest_balance = min(balances)
        return not insufficient_accounts, lowest_balance, insufficient_accounts

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

    def action_select_winning_rfq(self, winning_po):
        """Called by the RFQ price wizard once a winning quote has been selected.
        From here on, CXO and HOD approval happen directly on winning_po itself -
        this requisition just waits for that RFQ's approval flags to advance."""
        self.ensure_one()
        if self.state != 'rfq_sent':
            raise ValidationError(_('This request is not in RFQ Sent state.'))
        self.write({
            'selected_rfq_id': winning_po.id,
            'state': 'vendor_selected',
        })
        self.message_post(body=_(
            'Quote from %s selected. Awaiting CXO and HOD approval on that RFQ.'
        ) % winning_po.partner_id.display_name)

    def action_funds_available(self):
        """Decide whether funds are available for the selected quote."""
        self.ensure_one()
        if self.state != 'funds_check':
            raise ValidationError(_('This request is not in Funds Availability Check state.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_cfo_shariah'):
            raise ValidationError(_('Only CFO / Shariah Dept can decide fund availability.'))
        is_ok, balance, insufficient_accounts = self._get_shariah_funds_check()
        if not is_ok:
            raise ValidationError(_(
                'Shariah Law closing balance is insufficient for segment(s): %s '
                '(balance: %s). Use "Confirm Fund Transfer" instead once the '
                'CFO / Shariah Dept has transferred funds.'
            ) % (', '.join(insufficient_accounts.mapped('display_name')), balance))
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
        if not self.env.user.has_group('bn_procurement_workflow.group_cfo_shariah'):
            raise ValidationError(_('Only CFO / Shariah Dept can decide fund availability.'))
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

        button_confirm() (bn_purchase_customization) already requires the RFQ
        itself to be CXO and HOD approved, so this simply calls it - if
        someone reaches Funds Check without those two approvals recorded on
        the RFQ (which shouldn't be reachable through the normal flow, since
        this requisition's own state only advances to 'funds_check' once the
        RFQ is HOD approved), button_confirm() will raise and stop the
        release rather than silently skipping the check.
        """
        self.ensure_one()
        if not self.selected_rfq_id:
            raise ValidationError(_('No selected RFQ to release.'))
        self.selected_rfq_id.button_confirm()
        self.action_in_progress()
