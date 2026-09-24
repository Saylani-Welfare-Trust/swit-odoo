# -*- coding: utf-8 -*-
from collections import defaultdict

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
    # CFO budget approval
    # ------------------------------------------------------------------
    def _get_accounting_budget_rows(self):
        """Every (analytic account, budget, required, available) row of the
        accounting budget check, whether it is short or not. Checks the RFQ's own amounts against the accounting budget, the same
        way the Material Request does (available budget per analytic account and
        budget). The vendor's prices can differ from the Material Request's
        estimate that its CFO / COO approved, so the RFQ is checked again.
        Returns [(analytic account, budget, required, available)]."""
        self.ensure_one()
        request = self.material_request_id
        if not request:
            return []
        today = fields.Date.context_today(self)
        line_model = self.env['material.request.line']
        totals = defaultdict(float)
        for line in self.order_line:
            if not line.product_id:
                continue
            analytic = self._get_product_segment(line.product_id)
            if not analytic:
                continue
            request_line = request.line_ids.filtered(lambda l: l.product_id == line.product_id)[:1]
            budget = request_line.budget_id or line_model._get_default_budget_for_analytic(analytic)
            totals[(analytic, budget)] += line.price_subtotal
        rows = []
        for (analytic, budget), required in totals.items():
            budget_lines = self.env['budget.lines'].search([
                ('analytic_account_id', '=', analytic.id),
                ('budget_id', '=', budget.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ])
            available = sum(abs(l.practical_amount) for l in budget_lines)
            rows.append((analytic, budget, required, available))
        return rows

    def _get_accounting_budget_shortfalls(self):
        """The rows of the accounting budget check where the RFQ exceeds the budget."""
        self.ensure_one()
        return [row for row in self._get_accounting_budget_rows() if row[2] > row[3]]

    def _get_budget_check_summary(self):
        """Human-readable figures behind the budget check, so it is visible why an
        RFQ was (or was not) sent to the CFO."""
        self.ensure_one()
        lines = []
        if not self.material_request_id:
            lines.append(_('Accounting budget: not checked (no source Material Request).'))
        for analytic, budget, required, available in self._get_accounting_budget_rows():
            lines.append(_('Accounting budget %(budget)s / %(segment)s: RFQ %(required).2f, available %(available).2f') % {
                'budget': budget.display_name or _('none'), 'segment': analytic.display_name,
                'required': required, 'available': available})
        blocker = self.env['shariah.law.blocker'].get_blocker_config()
        if not (blocker and blocker.enable_purchase):
            lines.append(_('Shariah balance: NOT checked - "Purchase Orders" is switched off in the Shariah Law Blocker.'))
        else:
            amounts = self._get_shariah_amounts()
            if not amounts:
                lines.append(_('Shariah balance: nothing to check - none of the products belongs to a Shariah segment (analytic account).'))
            for analytic_id, required in amounts.items():
                analytic = self.env['account.analytic.account'].browse(analytic_id)
                lines.append(_('Shariah %(segment)s: RFQ %(required).2f, closing balance %(balance).2f') % {
                    'segment': analytic.display_name, 'required': required,
                    'balance': self.env['shariah.law'].get_closing_balance(analytic_id)})
        if self.shariah_override:
            lines.append(_('The CFO has already approved this RFQ, so the figures are not enforced.'))
        return lines

    def _get_budget_exceeded_reasons(self):
        """Why this RFQ needs the CFO's decision; empty when it is within the
        Shariah Law balance, or when the CFO has already approved it. The
        accounting budget is not checked here - the Material Request's own
        CFO / COO Budget Approval already covers that; this step only looks at
        Shariah. Checked on the RFQ's current amounts every time."""
        self.ensure_one()
        if self.shariah_override:
            return []
        return [
            _('%(segment)s: required %(required).2f, Shariah closing balance %(balance).2f') % {
                'segment': analytic.display_name, 'required': required, 'balance': balance}
            for analytic, required, balance in self._get_shariah_shortfalls()
        ]

    def _mark_cfo_approved(self, auto=False):
        """Record the CFO approval and let the requisition move on to the Funds
        Availability gate."""
        for order in self:
            order.write({
                'cfo_approved': True,
                'cfo_approved_by': False if auto else self.env.user.id,
                'cfo_approved_date': fields.Datetime.now(),
            })
            order.message_post(body=_('Within budget - CFO approval recorded automatically.')
                               if auto else _('CFO approved by %s.') % self.env.user.display_name)
            requisition = order.requisition_id
            if requisition and requisition.selected_rfq_id == order and requisition.state == 'cxo_approved':
                requisition.write({'state': 'funds_check'})
                requisition.message_post(body=_(
                    'CFO approval on the selected RFQ %s done - moving to Funds Availability check.'
                ) % order.name)

    def _release_to_po(self):
        """Turn the approved RFQ into a PO. For an RFQ picked in a Purchase
        Requisition this goes through the requisition's own release, so the
        requisition is marked as in progress too. A failure is reported on the
        RFQ instead of undoing the approval that triggered it - Confirm Order
        then stays available to do it by hand."""
        self.ensure_one()
        order = self.sudo()
        try:
            with self.env.cr.savepoint():
                requisition = order.requisition_id
                if requisition and requisition.selected_rfq_id == order:
                    requisition._release_po()
                else:
                    order.button_confirm()
        except UserError as e:
            self.message_post(body=_(
                'The PO could not be created automatically: %s<br/>Use Confirm Order once this is resolved.') % e)

    def _evaluate_cfo_stage(self):
        """Within budget: CFO approval is recorded automatically and the PO is
        created. Over budget: the RFQ waits for the CFO, who approves it or
        arranges the budget. Returns the RFQs that were put on hold."""
        held = self.browse()
        for order in self:
            reasons = order._get_budget_exceeded_reasons()
            if not reasons:
                order.message_post(body=_('Budget check - within budget:<br/>%s') % '<br/>'.join(order._get_budget_check_summary()))
                order._mark_cfo_approved(auto=True)
                order._release_to_po()
                continue
            reason = '\n'.join(reasons)
            order.write({'shariah_hold': True, 'shariah_hold_reason': reason})
            order._notify_cfo_approval_needed(reason)
            held |= order
        return held

    def action_open_arrange_budget(self):
        """CFO opens the wizard that moves budget in from other Shariah segments."""
        self.ensure_one()
        self._check_shariah_cfo()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Arrange Budget'),
            'res_model': 'procurement.arrange.budget.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def _after_budget_arranged(self, transfers):
        """Called once the CFO's Shariah transfers are done: when the RFQ now
        fits the balance it is approved and its PO created."""
        self.ensure_one()
        pending = transfers.filtered(lambda t: t.state != 'posted')
        if transfers:
            self.message_post(body=_('Budget arranged by %(user)s through Shariah transfer(s): %(names)s.') % {
                'user': self.env.user.display_name, 'names': ', '.join(transfers.mapped('name'))})
        if pending:
            self.message_post(body=_(
                'Waiting for Shariah member approval of: %s. Open Arrange Budget again once approved.'
            ) % ', '.join(pending.mapped('name')))
            return
        reasons = self._get_budget_exceeded_reasons()
        if reasons:
            reason = '\n'.join(reasons)
            self.write({'shariah_hold_reason': reason})
            self.message_post(body=_('The RFQ is still over budget.<br/>%s') % reason.replace('\n', '<br/>'))
            return
        self.write({'shariah_hold': False, 'shariah_hold_reason': False})
        self._mark_cfo_approved()
        self._release_to_po()

    def _notify_cfo_approval_needed(self, reason):
        """Ping every user who can give CFO approval (the Material Request CFO
        group) that this RFQ needs their action, two ways:
        - a chatter message addressed to them (inbox, and email per their own
          notification preference);
        - a "To Do" activity assigned to each of them, since that shows up on
          their own Activities view/dashboard even if they never open this RFQ
          from the chatter notification."""
        self.ensure_one()
        cfo_users = self.env.ref(CFO_GROUP).users
        body = _(
            'Budget exceeded - waiting for the CFO to approve it or arrange the budget.<br/>%s'
        ) % reason.replace('\n', '<br/>')
        self.message_post(
            body=body,
            partner_ids=cfo_users.partner_id.ids,
            subtype_xmlid='mail.mt_comment',
        )
        if not cfo_users:
            self.message_post(body=_(
                'No user currently holds the CFO approval group (%s) - nobody was notified.'
            ) % CFO_GROUP)
            return
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for user in cfo_users:
            self.activity_schedule(
                activity_type_id=activity_type.id if activity_type else False,
                summary=_('CFO approval needed: budget exceeded'),
                note=body,
                user_id=user.id,
            )

    def _shariah_hold_notification(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CFO Approval Required'),
                'message': _('The budget is exceeded (see the banner for the current figures). The RFQ waits for the CFO to approve it or arrange the budget.'),
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
        """CFO approves the RFQ despite the exceeded budget, and its PO is created.
        The amounts are checked again first: if they changed since the hold was
        raised, the CFO gets to review the new figures before approving."""
        self.ensure_one()
        self._check_shariah_cfo()
        reason = '\n'.join(self._get_budget_exceeded_reasons())
        if reason and reason != self.shariah_hold_reason:
            self.write({'shariah_hold_reason': reason})
            self.message_post(body=_(
                'The RFQ amounts changed while it was waiting for the CFO.<br/>%s'
            ) % reason.replace('\n', '<br/>'))
            return self._shariah_hold_notification()
        self.write({'shariah_hold': False, 'shariah_hold_reason': False, 'shariah_override': True})
        self._mark_cfo_approved()
        self._release_to_po()
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
        res = super().action_cxo_approve_po()
        for order in self:
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
        return res

    def action_hod_approve_po(self):
        """HOD approval. Then the budget decides the CFO stage: within budget the
        CFO approval is recorded automatically and the PO is created; over
        budget the RFQ waits for the CFO."""
        res = super().action_hod_approve_po()
        held = self._evaluate_cfo_stage()
        return self._shariah_hold_notification() if held else res

    def action_cfo_approve_po(self):
        """Manual CFO approval, for RFQs that got CXO and HOD approval before the
        automatic budget check existed. Same rules: within budget it is approved,
        over budget it waits for the CFO's decision."""
        if not self.env.user.has_group(CFO_GROUP):
            raise UserError(_('Only the CFO can give CFO approval.'))
        for order in self:
            if not (order.cxo_approved and order.hod_approved):
                raise UserError(_('CXO and HOD approval are required before CFO approval.'))
            if order.cfo_approved:
                raise UserError(_('RFQ %s is already CFO approved.') % order.display_name)
            if order.shariah_hold:
                raise UserError(_('RFQ %s is waiting for the CFO decision.') % order.display_name)
        held = self._evaluate_cfo_stage()
        return self._shariah_hold_notification() if held else True

    def button_confirm(self):
        for order in self:
            if not order.cfo_approved:
                raise UserError(_(
                    'RFQ %s cannot be confirmed until it has CFO approval.'
                ) % order.display_name)
        return super().button_confirm()
