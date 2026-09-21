# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

CFO_GROUP = 'bn_material_request.menu_group_material_request_cfo'


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Final approval before the RFQ can be confirmed into a PO (after CXO and HOD).
    cfo_approved = fields.Boolean('CFO Approved', copy=False, readonly=True, tracking=True)
    cfo_approved_by = fields.Many2one('res.users', string='CFO Approved By', readonly=True, copy=False)
    cfo_approved_date = fields.Datetime(string='CFO Approved On', readonly=True, copy=False)

    is_cxo_approver_allowed = fields.Boolean(
        compute='_compute_is_cxo_approver_allowed',
        help='Whether the current user may CXO-approve this RFQ: when it comes from a '
             'Material Request, only the user who gave that request its HOD approval can.')

    # The RFQ's state is left untouched while on hold (its CXO / HOD approval
    # flags carry its position in the flow), so once the CFO releases it the
    # flow simply carries on from where it stopped.
    shariah_hold = fields.Boolean(string='Shariah Hold', copy=False, readonly=True, tracking=True)
    shariah_hold_reason = fields.Text(string='Shariah Hold Reason', copy=False, readonly=True)

    @api.depends_context('uid')
    @api.depends('material_request_id.hod_approved_by')
    def _compute_is_cxo_approver_allowed(self):
        for order in self:
            hod_user = order.material_request_id.hod_approved_by
            order.is_cxo_approver_allowed = not hod_user or hod_user == self.env.user

    # ------------------------------------------------------------------
    # Shariah hold
    # ------------------------------------------------------------------
    def _shariah_gate(self):
        """Put every order exceeding the Shariah Law balance on hold and return
        the ones that may go ahead with the current approval step."""
        allowed = self.browse()
        held = self.browse()
        for order in self:
            if order.shariah_hold:
                raise UserError(_(
                    'RFQ %s is on Shariah Hold - only the CFO can approve or reject it.'
                ) % order.display_name)
            shortfalls = [] if order.shariah_override else order._get_shariah_shortfalls()
            if not shortfalls:
                allowed |= order
                continue
            reason = '\n'.join(
                _('%(segment)s: required %(required).2f, Shariah closing balance %(balance).2f') % {
                    'segment': analytic.display_name, 'required': required, 'balance': balance}
                for analytic, required, balance in shortfalls)
            order.write({'shariah_hold': True, 'shariah_hold_reason': reason})
            order.message_post(body=_(
                'Put on Shariah Hold - the amount exceeds the Shariah Law balance. '
                'Only the CFO can approve or reject it.<br/>%s') % reason.replace('\n', '<br/>'))
            held |= order
        return allowed, held

    def _shariah_hold_notification(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shariah Hold'),
                'message': _('The amount exceeds the Shariah Law balance. The RFQ is on hold until the CFO approves or rejects it.'),
                'type': 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _check_shariah_cfo(self):
        self.ensure_one()
        if not self.shariah_hold:
            raise UserError(_('This RFQ is not on Shariah Hold.'))
        if not self.env.user.has_group(CFO_GROUP):
            raise UserError(_('Only the CFO can approve or reject a Shariah Hold.'))

    def action_shariah_hold_approve(self):
        """CFO releases the hold; the RFQ carries on from the stage it was held at."""
        self.ensure_one()
        self._check_shariah_cfo()
        self.write({'shariah_hold': False, 'shariah_hold_reason': False, 'shariah_override': True})
        self.message_post(body=_('Shariah Hold approved by CFO %s.') % self.env.user.display_name)
        return True

    def action_shariah_hold_reject(self):
        """CFO rejects the held RFQ, which cancels it."""
        self.ensure_one()
        self._check_shariah_cfo()
        self.write({'shariah_hold': False, 'shariah_hold_reason': False})
        self.message_post(body=_('Shariah Hold rejected by CFO %s - RFQ cancelled.') % self.env.user.display_name)
        self.button_cancel()
        return True

    # ------------------------------------------------------------------
    # Approval steps
    # ------------------------------------------------------------------
    def action_cxo_approve_po(self):
        """CXO approval on this RFQ is the only CXO approval in the Procurement
        workflow - reflect it onto the requisition's own state so the PR
        doesn't need a second, duplicate CXO Approval step of its own.

        If the requisition doesn't have a selected RFQ yet, approving one
        here claims it as the winning quote - this doesn't require having
        gone through the Bulk RFQ Price wizard's "Confirm Selected Lines"
        first, since that's an easy step to miss when there's only one
        vendor to compare anyway.

        When the RFQ comes from a Material Request, only the user who gave that
        request its HOD approval may do this CXO approval."""
        for order in self:
            hod_user = order.material_request_id.hod_approved_by
            if hod_user and hod_user != self.env.user:
                raise UserError(_(
                    'Only %(user)s, who gave HOD approval to Material Request %(request)s, '
                    'can give CXO approval to this RFQ.'
                ) % {'user': hod_user.display_name, 'request': order.material_request_id.name})
        allowed, held = self._shariah_gate()
        res = super(PurchaseOrder, allowed).action_cxo_approve_po() if allowed else None
        for order in allowed:
            requisition = order.requisition_id
            if not requisition or not requisition.material_request_id:
                continue
            if requisition.state == 'rfq_sent' and not requisition.selected_rfq_id:
                requisition.write({'selected_rfq_id': order.id, 'state': 'cxo_approved'})
                requisition.message_post(body=_(
                    'RFQ %s approved by CXO and claimed as the selected quote.'
                ) % order.name)
            elif requisition.selected_rfq_id == order and requisition.state == 'vendor_selected':
                requisition.write({'state': 'cxo_approved'})
                requisition.message_post(body=_('CXO approved the selected RFQ %s.') % order.name)
        return self._shariah_hold_notification() if held else res

    def action_hod_approve_po(self):
        """HOD approval; the requisition then waits for the CFO's approval of
        this RFQ before moving to the Funds Availability gate."""
        # Orders without CXO approval are left to super(), which rejects them
        # before any Shariah check is worth doing.
        allowed, held = self.filtered('cxo_approved')._shariah_gate()
        allowed |= self - self.filtered('cxo_approved')
        res = super(PurchaseOrder, allowed).action_hod_approve_po() if allowed else None
        for order in allowed:
            requisition = order.requisition_id
            if requisition and requisition.selected_rfq_id == order and requisition.state == 'cxo_approved':
                requisition.message_post(body=_(
                    'HOD approved the selected RFQ %s - awaiting CFO approval on that RFQ.'
                ) % order.name)
        return self._shariah_hold_notification() if held else res

    def action_cfo_approve_po(self):
        """CFO approval on the RFQ, needed before it can be confirmed into a
        PO. Once given on the winning RFQ, the requisition moves to the Funds
        Availability gate."""
        for order in self:
            if not self.env.user.has_group(CFO_GROUP):
                raise UserError(_('Only the CFO can give CFO approval.'))
            if not (order.cxo_approved and order.hod_approved):
                raise UserError(_('CXO and HOD approval are required before CFO approval.'))
            if order.cfo_approved:
                raise UserError(_('RFQ %s is already CFO approved.') % order.display_name)
        allowed, held = self._shariah_gate()
        allowed.write({
            'cfo_approved': True,
            'cfo_approved_by': self.env.user.id,
            'cfo_approved_date': fields.Datetime.now(),
        })
        for order in allowed:
            requisition = order.requisition_id
            if requisition and requisition.selected_rfq_id == order and requisition.state == 'cxo_approved':
                requisition.write({'state': 'funds_check'})
                requisition.message_post(body=_(
                    'CFO approved the selected RFQ %s - moving to Funds Availability check.'
                ) % order.name)
        return self._shariah_hold_notification() if held else True

    def button_confirm(self):
        for order in self:
            if not order.cfo_approved:
                raise UserError(_(
                    'RFQ %s cannot be confirmed until it has CFO approval.'
                ) % order.display_name)
        allowed, held = self._shariah_gate()
        res = super(PurchaseOrder, allowed).button_confirm() if allowed else None
        return self._shariah_hold_notification() if held else res
