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

    # NEW FIELD: Assign a specific person to approve this RFQ from the Master Setup list
    designated_cxo_approver_id = fields.Many2one(
        'master.cxo.approver', 
        string='Assigned CXO Approver', 
        tracking=True,
        help='If set, ONLY this user can give CXO approval to this RFQ.'
    )

    is_cxo_approver_allowed = fields.Boolean(
        compute='_compute_is_cxo_approver_allowed',
        help='Whether the current user may CXO-approve this RFQ.')

    # The RFQ's state is left untouched while on hold
    shariah_hold = fields.Boolean(string='Shariah Hold', copy=False, readonly=True, tracking=True)
    shariah_hold_reason = fields.Text(string='Shariah Hold Reason', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Notify the designated CXO approver by email
    # ------------------------------------------------------------------
    def _send_cxo_approval_email(self):
        """Send the 'please approve' email to the assigned approver's
        work_email. Silently skips if no approver / no email."""
        self.ensure_one()
        approver = self.designated_cxo_approver_id
        if not approver:
            return
        if not approver.work_email:
            self.message_post(body=_(
                'No work email set for the assigned CXO approver (%s) - '
                'email notification skipped.'
            ) % approver.employee_id.name)
            return

        template = self.env.ref(APPROVAL_TEMPLATE, raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Fallback if the XML template was not installed
            self.env['mail.mail'].create({
                'subject': _('Approval Required: %s') % (self.name or self.display_name),
                'email_to': approver.work_email,
                'email_from': self.company_id.email or self.env.user.email,
                'model': self._name,
                'res_id': self.id,
                'body_html': _(
                    '<p>Dear %(name)s,</p>'
                    '<p>Purchase order <strong>%(po)s</strong> needs your CXO approval.</p>'
                    '<p>Amount: %(currency)s %(amount).2f</p>'
                ) % {
                    'name': approver.employee_id.name,
                    'po': self.name or self.display_name,
                    'currency': self.currency_id.name,
                    'amount': self.amount_total,
                },
            }).send()

        self.message_post(body=_(
            'CXO approval request emailed to %(name)s &lt;%(email)s&gt;.'
        ) % {
            'name': approver.employee_id.name,
            'email': approver.work_email,
        })

    # ------------------------------------------------------------------
    # Trigger the email whenever the approver is (re)assigned
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if order.designated_cxo_approver_id:
                order._send_cxo_approval_email()
        return orders

    def write(self, vals):
        old_approvers = {}
        if 'designated_cxo_approver_id' in vals:
            old_approvers = {rec.id: rec.designated_cxo_approver_id for rec in self}

        res = super().write(vals)

        if 'designated_cxo_approver_id' in vals:
            for order in self:
                new_approver = order.designated_cxo_approver_id
                if new_approver and new_approver != old_approvers.get(order.id):
                    order._send_cxo_approval_email()
        return res

    # Optional: a manual "resend" button
    def action_resend_cxo_approval_email(self):
        for order in self:
            if not order.designated_cxo_approver_id:
                raise UserError(_('No CXO approver is assigned to %s.') % order.display_name)
            order._send_cxo_approval_email()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email Sent'),
                'message': _('Approval email has been sent to the assigned approver.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.depends_context('uid')
    @api.depends('designated_cxo_approver_id', 'material_request_id.hod_approved_by')
    def _compute_is_cxo_approver_allowed(self):
        for order in self:
            if order.designated_cxo_approver_id:
                # If an approver is assigned, ONLY they can approve
                order.is_cxo_approver_allowed = (order.designated_cxo_approver_id.user_id == self.env.user)
            else:
                # Fallback to the original HOD rule
                hod_user = order.material_request_id.sudo().hod_approved_by
                order.is_cxo_approver_allowed = not hod_user or hod_user == self.env.user

    # ------------------------------------------------------------------
    # CFO budget approval (Unchanged)
    # ------------------------------------------------------------------
    def _get_accounting_budget_rows(self):
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
            request_line = request.sudo().line_ids.filtered(lambda l: l.product_id == line.product_id)[:1]
            budget = request_line.budget_id.sudo(False) or line_model._get_default_budget_for_analytic(analytic)
            totals[(analytic, budget)] += line.price_subtotal
        rows = []
        for (analytic, budget), required in totals.items():
            budget_lines = self.env['budget.lines'].sudo().search([
                ('analytic_account_id', '=', analytic.id),
                ('budget_id', '=', budget.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ])
            available = sum(abs(l.practical_amount) for l in budget_lines)
            rows.append((analytic, budget, required, available))
        return rows

    def _get_accounting_budget_shortfalls(self):
        self.ensure_one()
        return [row for row in self._get_accounting_budget_rows() if row[2] > row[3]]

    def _get_budget_check_summary(self):
        self.ensure_one()
        lines = []
        if not self.material_request_id:
            lines.append(_('Accounting budget: not checked (no source Material Request).'))
        for analytic, budget, required, available in self._get_accounting_budget_rows():
            lines.append(_('Accounting budget %(budget)s / %(segment)s: RFQ %(required).2f, available %(available).2f') % {
                'budget': budget.sudo().display_name or _('none'), 'segment': analytic.display_name,
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
        self.ensure_one()
        if self.shariah_override:
            return []
        return [
            _('%(segment)s: required %(required).2f, Shariah closing balance %(balance).2f') % {
                'segment': analytic.display_name, 'required': required, 'balance': balance}
            for analytic, required, balance in self._get_shariah_shortfalls()
        ]

    def _mark_cfo_approved(self, auto=False):
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
        self.ensure_one()
        cfo_users = self.env.ref(CFO_GROUP).users
        body = _(
            'Budget exceeded on RFQ %(rfq)s - waiting for the CFO to approve it or arrange the budget.<br/>%(reason)s'
        ) % {'rfq': self.display_name, 'reason': reason.replace('\n', '<br/>')}
        if not cfo_users:
            self.message_post(body=_(
                'No user currently holds the CFO approval group (%s) - nobody was notified.'
            ) % CFO_GROUP)
            return
        cfo_users.filtered(lambda u: u.notification_type != 'inbox').notification_type = 'inbox'
        self.message_notify(
            body=body,
            partner_ids=cfo_users.partner_id.ids,
            subject=_('CFO Approval Required'),
        )
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
        self.ensure_one()
        self._check_shariah_cfo()
        self.write({'shariah_hold': False, 'shariah_hold_reason': False})
        self.message_post(body=_('Shariah Hold rejected by CFO %s - RFQ cancelled.') % self.env.user.display_name)
        self.button_cancel()
        return True

    # ------------------------------------------------------------------
    # Approval steps (UPDATED)
    # ------------------------------------------------------------------
    def action_cxo_approve_po(self):
        """CXO approval on this RFQ."""
        for order in self:
            # 1. Check the new designated approver first
            if order.designated_cxo_approver_id:
                if order.designated_cxo_approver_id.user_id != self.env.user:
                    raise UserError(_(
                        'Only the assigned approver, %s, can give CXO approval to this RFQ.'
                    ) % order.designated_cxo_approver_id.user_id.name)
            else:
                # 2. Fallback to the original HOD rule if no one is specifically assigned
                request = order.material_request_id.sudo()
                hod_user = request.hod_approved_by
                if hod_user and hod_user != self.env.user:
                    raise UserError(_(
                        'Only %(user)s, who gave HOD approval to Material Request %(request)s, '
                        'can give CXO approval to this RFQ.'
                    ) % {'user': hod_user.display_name, 'request': request.name})
                    
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
        res = super().action_hod_approve_po()
        held = self._evaluate_cfo_stage()
        return self._shariah_hold_notification() if held else res

    def action_cfo_approve_po(self):
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

    def button_approve(self, force=False):
        pending = self.filtered(lambda order: order.state not in ('purchase', 'done'))
        res = super().button_approve(force=force)
        pending.filtered(lambda order: order.state in ('purchase', 'done'))._close_purchase_request()
        return res

    def _close_purchase_request(self):
        for order in self:
            requisition = order.requisition_id.sudo()
            if not requisition or requisition.state in ('done', 'cancel'):
                continue
            if requisition.state == 'ongoing' or (
                    requisition.type_id.quantity_copy == 'none' and requisition.vendor_id):
                continue
            other_rfqs = requisition._cancel_other_rfqs(order, _(
                'Cancelled - %(order)s was confirmed for Purchase Request %(request)s.'
            ) % {'order': order.display_name, 'request': requisition.display_name})
            requisition.action_done()
            requisition.message_post(body=_(
                'Closed - Purchase Order %(order)s confirmed. %(count)s other RFQ(s) cancelled.'
            ) % {'order': order.display_name, 'count': len(other_rfqs)})