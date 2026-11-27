# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain


# states in which RFQs are still created for the products not on an RFQ yet
REMAINING_RFQ_STATES = ('rfq_sent', 'vendor_selected', 'cxo_approved', 'funds_check', 'in_progress', 'done')

class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    # only the contacts tagged Vendor
    vendor_id = fields.Many2one(domain=tag_domain('vendor'))

    requesting_department_id = fields.Many2one(
        related='material_request_id.department_id',
        string='Requesting Department', store=True, readonly=True)

    # Procurement Manager review / defer
    procurement_manager_id = fields.Many2one('res.users', string='Procurement Manager', readonly=True, copy=False)
    procurement_review_date = fields.Datetime(readonly=True, copy=False)
    defer_reason = fields.Text(string='Deferral Reason')

    # Who creates the RFQs: once someone is assigned, only they can select the
    # vendors (Vendor Selection Wizard) for this request. Chosen from the RFQ
    # Assignee List (Master Setup), see allowed_assignee_employee_ids.
    assigned_employee_ids = fields.Many2many(
        'hr.employee', 'purchase_requisition_assigned_employee_rel', 'requisition_id', 'employee_id',
        string='Assigned To', tracking=True, copy=False,
        domain=[('user_id', '!=', False)],
        help='Employees who create the RFQs of this request. Once set, only these '
             'employees can select the vendors for its RFQs.')
    # Stored, so that users without HR access can be matched against it.
    assigned_user_ids = fields.Many2many(
        'res.users', 'purchase_requisition_assigned_user_rel', 'requisition_id', 'user_id',
        string='Assigned Users', compute='_compute_assigned_user_ids', store=True)
    # The employees of the RFQ Assignee List: the ones "Assigned To" offers.
    # An id domain, because users without HR access search hr.employee.public.
    allowed_assignee_employee_ids = fields.Many2many(
        'hr.employee', compute='_compute_allowed_assignee_employee_ids')
    assigned_by_id = fields.Many2one('res.users', string='Assigned By', readonly=True, copy=False)
    is_rfq_creator_allowed = fields.Boolean(
        compute='_compute_is_rfq_creator_allowed',
        help='Whether the current user may select the vendors for the RFQs of this request.')

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

    # The Purchase Order may cover only part of what the Material Request asks
    # for (fewer products, or a lower quantity), which leaves the request
    # closed with something that was never ordered. The RFQs may also have
    # been sent out for less than the Material Request asks for.
    has_pending_rfq_products = fields.Boolean(
        compute='_compute_has_pending_rfq_products',
        help='Whether the Material Request asks for products or quantities that '
             'are not on an RFQ yet, and no more recent Purchase Request has been '
             'created for them.')
    # Lines (or part of their quantity) not yet sent out on an RFQ: more RFQs
    # are created for them on this same requisition, until it is closed.
    has_lines_to_rfq = fields.Boolean(
        compute='_compute_has_lines_to_rfq',
        help='Whether some of its lines have not been sent out on an RFQ yet.')

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
        insufficient_accounts = self.env['account.analytic.account']
        if not self.selected_rfq_id:
            return True, 0.0, insufficient_accounts
        balances = []
        # {segment id: subtotal of the RFQ's lines on it}, each line going to
        # the analytic account set on its product
        for analytic_id, required in self.selected_rfq_id._get_shariah_amounts().items():
            balance = shariah_law.get_closing_balance(analytic_id)
            balances.append(balance)
            if required > balance:
                insufficient_accounts |= insufficient_accounts.browse(analytic_id)
        return not insufficient_accounts, min(balances, default=0.0), insufficient_accounts

    @api.depends('assigned_employee_ids.user_id')
    def _compute_assigned_user_ids(self):
        for requisition in self:
            requisition.assigned_user_ids = requisition.assigned_employee_ids.user_id

    def _compute_allowed_assignee_employee_ids(self):
        employees = self.env['master.rfq.assignee'].search([]).employee_id
        for requisition in self:
            requisition.allowed_assignee_employee_ids = employees

    @api.depends_context('uid')
    @api.depends('assigned_employee_ids', 'assigned_user_ids')
    def _compute_is_rfq_creator_allowed(self):
        for requisition in self:
            requisition.is_rfq_creator_allowed = (
                not requisition.assigned_employee_ids or self.env.user in requisition.assigned_user_ids)

    def _check_rfq_creator(self):
        for requisition in self:
            if not requisition.is_rfq_creator_allowed:
                raise ValidationError(_(
                    'Only %(employees)s, assigned to Purchase Request %(request)s, can select the vendors for its RFQs.',
                    employees=', '.join(requisition.sudo().assigned_employee_ids.mapped('name')),
                    request=requisition.name))

    @api.model_create_multi
    def create(self, vals_list):
        requisitions = super().create(vals_list)
        assigned = requisitions.filtered('assigned_employee_ids')
        assigned.write({'assigned_by_id': self.env.uid})
        assigned._notify_assigned_users()
        return requisitions

    def write(self, vals):
        old_users = {}
        if 'assigned_employee_ids' in vals:
            old_users = {requisition.id: requisition.assigned_user_ids for requisition in self}
        res = super().write(vals)
        if 'assigned_employee_ids' in vals:
            # the field is written with x2many commands: whether anyone is
            # still assigned is only known once they are applied
            assigned = self.filtered('assigned_employee_ids')
            assigned.write({'assigned_by_id': self.env.uid})
            (self - assigned).write({'assigned_by_id': False})
            self._notify_assigned_users(old_users)
        if 'picking_type_id' in vals:
            self._sync_operation_type_to_rfqs()
        return res

    def _get_open_rfqs(self):
        """RFQs of these requests not confirmed yet: their own, and the
        consolidated ones they contributed lines to (requisition_ids)."""
        orders = self.purchase_ids | self.env['purchase.order'].search(
            [('requisition_ids', 'in', self.ids)])
        return orders.filtered(lambda order: order.state in ('draft', 'sent', 'to approve'))

    def _sync_operation_type_to_rfqs(self):
        """The Operation Type of a Purchase Request is the one its RFQs - and the
        Purchase Order they become - receive the products with. A confirmed
        Purchase Order keeps its own: its receipts are already created."""
        # sudo: the RFQs may be outside what the user editing the request can write
        for requisition in self.sudo():
            rfqs = requisition._get_open_rfqs().filtered(
                lambda order: order.picking_type_id != requisition.picking_type_id)
            # skip_operation_type_sync: not sent back up to the requests
            rfqs.with_context(skip_operation_type_sync=True).write(
                {'picking_type_id': requisition.picking_type_id.id})

    def _notify_assigned_users(self, old_users=None):
        """A message in the Discuss inbox of each newly assigned employee: the
        request now waits for them to create its RFQs. Also sent to someone
        assigning themselves (mail_notify_author: Odoo leaves the author out
        otherwise).

        :param dict old_users: {requisition id: users assigned before}, who are
            not notified again
        """
        old_users = old_users or {}
        for requisition in self:
            users = requisition.assigned_user_ids - old_users.get(requisition.id, self.env['res.users'])
            if not users:
                continue
            # Inbox, so the message shows in Discuss rather than as an email.
            requisition.with_context(mail_notify_author=True).message_notify(
                body=_('Purchase Request %(request)s has been assigned to you by %(user)s to create its RFQs.',
                       request=requisition.display_name, user=self.env.user.display_name),
                partner_ids=users.partner_id.ids,
                subject=_('Purchase Request Assigned'),
            )

    def _can_create_rfqs(self):
        """The first RFQs in Procurement Manager Approval; later ones, for the
        products not on an RFQ yet, from RFQ Sent on ("Create RFQs for Remaining
        Products" shows in the same states)."""
        self.ensure_one()
        return self.state == 'procurement_approval' or (
            self.state in REMAINING_RFQ_STATES and self.has_lines_to_rfq)

    def action_create_multi_vendor_rfqs(self):
        self._check_rfq_creator()
        if not self._can_create_rfqs():
            raise ValidationError(_('RFQs cannot be created for this request in its current state.'))
        return super().action_create_multi_vendor_rfqs()

    def action_procurement_approve(self):
        """Procurement Manager reviews and approves the draft PR directly - no HOD/Member
        approval step in this workflow. Moves the PR into its own 'Procurement Manager
        Approval' state, which unlocks RFQ creation."""
        self.ensure_one()
        # Confirm (a request entered by hand), or Draft (a request created for
        # the remaining products of a Material Request)
        if self.state not in ('draft', 'confirm'):
            raise ValidationError(_('This request is not waiting for Procurement Manager approval.'))
        if not self.env.su and not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can approve this request.'))
        # The request gets its number here, so that the RFQs sent out next carry it.
        self._assign_reference_number()
        self.write({
            'procurement_manager_id': self.env.user.id,
            'procurement_review_date': fields.Datetime.now(),
            'state': 'procurement_approval',
        })
        self.message_post(body=_('Approved by Procurement Manager - ready for RFQs to be sent to vendors.'))

    def action_open_defer_wizard(self):
        """Open the small popup collecting the mandatory deferral reason."""
        self.ensure_one()
        if self.state not in ('draft', 'confirm'):
            raise ValidationError(_('Only a request waiting for Procurement Manager approval can be deferred.'))
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
        if self.state not in ('draft', 'confirm'):
            raise ValidationError(_('Only a request waiting for Procurement Manager approval can be deferred.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can defer this request.'))
        if not reason:
            raise ValidationError(_('Please provide a deferral reason.'))
        self.write({'state': 'deferred', 'defer_reason': reason})
        self.message_post(body=_('Purchase Requisition deferred by Procurement Manager.\nReason: %s') % reason)

    def action_procurement_resume(self):
        """Resume a deferred PR back to Confirm for Procurement Manager review."""
        self.ensure_one()
        if self.state != 'deferred':
            raise ValidationError(_('This request is not Deferred.'))
        if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
            raise ValidationError(_('Only a Procurement Manager can resume this request.'))
        self.state = 'confirm'

    @api.depends('material_request_id', 'state', 'purchase_ids.state',
                 'purchase_ids.order_line.product_id', 'purchase_ids.order_line.product_qty',
                 'line_ids.product_id', 'line_ids.product_qty')
    def _compute_has_pending_rfq_products(self):
        """The RFQs of the Material Request are matched against it, product by
        product and quantity by quantity: any difference is pending, and once
        every product and quantity is on an RFQ nothing is. Only the latest
        requisition of a Material Request offers to act on it, so the same
        remainder is never requested twice."""
        for requisition in self:
            requisition.has_pending_rfq_products = bool(
                requisition.material_request_id
                and not requisition._has_newer_request()
                and requisition._get_request_shortfall())

    @api.depends('line_ids.is_locked')
    def _compute_has_lines_to_rfq(self):
        for requisition in self:
            requisition.has_lines_to_rfq = bool(requisition._get_lines_to_rfq())

    def _get_lines_to_rfq(self):
        """Lines not yet fully sent out on an RFQ. A requisition whose RFQs were
        all created before lines were locked has no line locked at all, and is
        treated as having none left - unless those RFQs are all cancelled."""
        self.ensure_one()
        if not any(line.locked_qty for line in self.line_ids) and \
                self.sudo().purchase_ids.filtered(lambda rfq: rfq.state != 'cancel'):
            return self.line_ids.browse()
        return self.line_ids.filtered(lambda line: not line.is_locked)

    def _is_selecting_rfqs(self):
        """Whether a winning quote can be selected for this requisition. Each
        product gets its own winner: the first is selected in RFQ Sent - or
        still in Procurement Manager Approval, while some products are not on
        an RFQ yet - and the others any time after that until the requisition
        is closed."""
        self.ensure_one()
        return self.state in ('procurement_approval', 'rfq_sent') or bool(
            self.selected_rfq_id and self.state not in ('done', 'cancel'))

    def action_select_winning_rfq(self, winning_pos):
        """Called by the RFQ price wizard once winning quotes have been selected:
        one per product, or several vendors each given a share of a product's
        quantity. The first winner becomes this requisition's selected RFQ,
        whose approval progress its state follows; the other winners only
        cancel the quotes competing with them. From here on, CXO and HOD
        approval happen directly on each winning RFQ."""
        self.ensure_one()
        if not self._is_selecting_rfqs():
            raise ValidationError(_('A winning quote cannot be selected for this request in its current state.'))
        for winning_po in winning_pos.filtered(lambda po: not po.is_selected_quote):
            winning_po.write({
                'is_selected_quote': True,
                'selected_quote_by': self.env.user.id,
                'selected_quote_date': fields.Datetime.now(),
            })
            # Held back until now: the approver can only act once it is selected.
            if winning_po.designated_cxo_approver_id:
                winning_po._send_cxo_approval_email()
        if not self.selected_rfq_id:
            self.write({
                'selected_rfq_id': winning_pos[0].id,
                'state': 'vendor_selected',
            })
        vendors = ', '.join(winning_pos.partner_id.mapped('display_name'))
        other_rfqs = self._cancel_other_rfqs(winning_pos, _(
            'Cancelled - the quote(s) of %(vendor)s were selected for Purchase Request %(request)s.'
        ) % {'vendor': vendors, 'request': self.display_name})
        self.message_post(body=_(
            'Quote(s) from %(vendor)s selected, %(count)s other RFQ(s) cancelled. '
            'Awaiting CXO and HOD approval on the selected RFQ(s).'
        ) % {'vendor': vendors, 'count': len(other_rfqs)})

    def _cancel_other_rfqs(self, kept_rfqs, message):
        """Cancel the other vendors' quotes, still open, for any product of
        ``kept_rfqs``, posting ``message`` on each of them. Quotes for this
        requisition's other products stay open, and so do the selected ones:
        the vendors a product is split between each have their share of it.
        Returns the cancelled RFQs."""
        self.ensure_one()
        products = kept_rfqs.order_line.product_id
        # sudo: whoever selects or approves the quote need not be a purchase user.
        other_rfqs = self.sudo().purchase_ids.filtered(
            lambda rfq: rfq not in kept_rfqs and not rfq.is_selected_quote
            and rfq.state in ('draft', 'sent', 'to approve')
            and rfq.order_line.product_id & products)
        if other_rfqs:
            # An RFQ waiting for the CFO must not keep its "Waiting for CFO" banner once cancelled.
            other_rfqs.write({'shariah_hold': False, 'shariah_hold_reason': False})
            other_rfqs.button_cancel()
            for rfq in other_rfqs:
                rfq.message_post(body=message)
        return other_rfqs

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

    def _follow_cancelled_selected_rfq(self):
        """The request follows its selected RFQ through CXO / CFO approval and
        the funds check. Once that RFQ is cancelled, it follows another winning
        quote still open - at whatever approval that one has reached - or goes
        back to RFQ Sent, for a new quote to be selected (its products are
        available again for new RFQs: bn_material_request)."""
        for requisition in self.filtered(
                lambda r: r.selected_rfq_id.state == 'cancel'
                and r.state in ('vendor_selected', 'cxo_approved', 'funds_check', 'in_progress')):
            cancelled = requisition.selected_rfq_id
            winner = requisition.purchase_ids.filtered(
                lambda rfq: rfq.is_selected_quote and rfq.state in ('draft', 'sent', 'to approve'))[:1]
            if winner:
                state = 'funds_check' if winner.cfo_approved else (
                    'cxo_approved' if winner.cxo_approved else 'vendor_selected')
                message = _('Selected RFQ %(cancelled)s cancelled - following the other winning quote %(winner)s.')
            else:
                state = 'rfq_sent'
                message = _('Selected RFQ %(cancelled)s cancelled - back to RFQ Sent, for a new quote to be selected.')
            requisition.write({
                'selected_rfq_id': winner.id,
                'state': state,
                'funds_available': False,
                'funds_gate_approver_id': False,
                'funds_gate_date': False,
            })
            requisition.message_post(body=message % {
                'cancelled': '%s (%s)' % (cancelled.name, cancelled.partner_id.name),
                'winner': '%s (%s)' % (winner.name, winner.partner_id.name)})

    @api.model
    def _backfill_cancelled_selected_rfq(self):
        """Run on upgrade: requests whose selected RFQ was cancelled before
        they followed it."""
        self.sudo().search([('selected_rfq_id.state', '=', 'cancel')])._follow_cancelled_selected_rfq()

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
        """Confirm the winning RFQ, which closes the requisition
        (purchase.order._close_purchase_request()).

        button_confirm() (bn_purchase_customization) already requires the RFQ
        itself to be CXO and HOD approved, so this simply calls it - if
        someone reaches Funds Check without those two approvals recorded on
        the RFQ (which shouldn't be reachable through the normal flow, since
        this requisition's own state only advances to 'funds_check' once the
        RFQ is CFO approved), button_confirm() will raise and stop the
        release rather than silently skipping the check.
        """
        self.ensure_one()
        if not self.selected_rfq_id:
            raise ValidationError(_('No selected RFQ to release.'))
        if not self.selected_rfq_id.cfo_approved:
            raise ValidationError(_('The selected RFQ needs CFO approval before it can be released.'))
        # The CFO / Shariah Dept has just made the funds decision for this RFQ
        # at the gate, so it must not be put on a second Shariah Hold here.
        self.selected_rfq_id.shariah_override = True
        # Before the confirmation, not after: it would reopen the requisition
        # if it ran once the PO has closed it.
        self.action_in_progress()
        self.selected_rfq_id.button_confirm()


class PurchaseRequisitionStepActivity(models.Model):
    """Activity for whoever has to act next (step.activity.mixin)."""
    _name = 'purchase.requisition'
    _inherit = ['step.activity.mixin', 'purchase.requisition']
