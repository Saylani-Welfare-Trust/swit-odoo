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

    # Who creates the RFQs: once someone is assigned, only they can select the
    # vendors (Vendor Selection Wizard) for this request.
    assigned_employee_id = fields.Many2one(
        'hr.employee', string='Assigned To', tracking=True, copy=False,
        domain=[('user_id', '!=', False)],
        help='Employee who creates the RFQs of this request. Once set, only this '
             'employee can select the vendors for its RFQs.')
    # Stored, so that users without HR access can be matched against it.
    assigned_user_id = fields.Many2one(
        related='assigned_employee_id.user_id', string='Assigned User', store=True)
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

    @api.depends_context('uid')
    @api.depends('assigned_employee_id', 'assigned_user_id')
    def _compute_is_rfq_creator_allowed(self):
        for requisition in self:
            requisition.is_rfq_creator_allowed = (
                not requisition.assigned_employee_id or requisition.assigned_user_id == self.env.user)

    def _check_rfq_creator(self):
        for requisition in self:
            if not requisition.is_rfq_creator_allowed:
                raise ValidationError(_(
                    'Only %(employee)s, assigned to Purchase Request %(request)s, can select the vendors for its RFQs.',
                    employee=requisition.sudo().assigned_employee_id.name, request=requisition.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('assigned_employee_id'):
                vals['assigned_by_id'] = self.env.uid
        return super().create(vals_list)

    def write(self, vals):
        if 'assigned_employee_id' in vals:
            vals = dict(vals, assigned_by_id=self.env.uid if vals['assigned_employee_id'] else False)
        return super().write(vals)

    def action_create_multi_vendor_rfqs(self):
        self._check_rfq_creator()
        return super().action_create_multi_vendor_rfqs()

    def action_procurement_approve(self):
        """Procurement Manager reviews and approves the draft PR directly - no HOD/Member
        approval step in this workflow. Moves the PR into its own 'Procurement Manager
        Approval' state, which unlocks RFQ creation."""
        self.ensure_one()
        # if self.state != 'confirm':
        #     raise ValidationError(_('This request is not in confirm state.'))
        # if not self.env.user.has_group('bn_procurement_workflow.group_procurement_manager'):
        #     raise ValidationError(_('Only a Procurement Manager can approve this request.'))
        if not self.material_request_id:
            raise ValidationError(
                _('This Purchase Requisition has no source Material Request, so there is no '
                  'requesting department to run Technical Evaluation against. It cannot enter '
                  'the Procurement workflow.'))
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
        treated as having none left."""
        self.ensure_one()
        if not any(line.locked_qty for line in self.line_ids):
            return self.line_ids.browse()
        return self.line_ids.filtered(lambda line: not line.is_locked)

    def action_create_remaining_request(self):
        """A closed request whose Purchase Order covers only part of its Material
        Request: create a new Purchase Request for the products and quantities
        that are not on an RFQ yet. This one is left as it is. While a request
        is open, its remaining products get their RFQs on it instead. The new
        one starts in Procurement Manager Approval, ready for RFQs: the
        Procurement Manager creating it is the one who would approve it."""
        self.ensure_one()
        if self.state != 'done':
            raise ValidationError(_(
                'This request is still open: create the RFQs for its remaining products on it instead.'))
        if not self.material_request_id:
            raise ValidationError(_('This Purchase Requisition has no source Material Request.'))
        if self._has_newer_request():
            raise ValidationError(_('A more recent Purchase Request already exists for this Material Request.'))
        shortfall = self._get_request_shortfall()
        if not shortfall:
            raise ValidationError(_('Every product and quantity of the Material Request is already on an RFQ.'))
        new_request = self._create_remaining_request()
        new_request.action_procurement_approve()
        products = ', '.join(
            '%s (%g %s)' % (product.display_name, quantity, product.uom_id.name)
            for product, quantity in shortfall.items())
        self.message_post(body=_(
            '%(user)s created %(request)s for what is not on an RFQ yet: %(products)s.',
            user=self.env.user.display_name,
            request=new_request._get_html_link(), products=products))
        new_request.message_post(body=_(
            'Created from %(request)s for what the Material Request still needs: %(products)s.',
            request=self._get_html_link(), products=products))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'purchase.requisition',
            'res_id': new_request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _is_selecting_rfqs(self):
        """Whether a winning quote can be selected for this requisition. Each
        product gets its own winner: the first is selected in RFQ Sent, and
        the others any time after that until the requisition is closed."""
        self.ensure_one()
        return self.state == 'rfq_sent' or bool(
            self.selected_rfq_id and self.state not in ('done', 'cancel'))

    def action_select_winning_rfq(self, winning_po):
        """Called by the RFQ price wizard once a winning quote has been selected.
        The first winner becomes this requisition's selected RFQ, whose approval
        progress its state follows; winners for its other products only cancel
        the quotes competing with them. From here on, CXO and HOD approval
        happen directly on winning_po itself."""
        self.ensure_one()
        if not self._is_selecting_rfqs():
            raise ValidationError(_('This request is not in RFQ Sent state.'))
        if not winning_po.is_selected_quote:
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
                'selected_rfq_id': winning_po.id,
                'state': 'vendor_selected',
            })
        other_rfqs = self._cancel_other_rfqs(winning_po, _(
            'Cancelled - the quote of %(vendor)s was selected for Purchase Request %(request)s.'
        ) % {'vendor': winning_po.partner_id.display_name, 'request': self.display_name})
        self.message_post(body=_(
            'Quote from %(vendor)s selected, %(count)s other RFQ(s) cancelled. '
            'Awaiting CXO and HOD approval on that RFQ.'
        ) % {'vendor': winning_po.partner_id.display_name, 'count': len(other_rfqs)})

    def _cancel_other_rfqs(self, kept_rfq, message):
        """Cancel the other vendors' quotes, still open, for any product of
        ``kept_rfq``, posting ``message`` on each of them. Quotes for this
        requisition's other products stay open. Returns the cancelled RFQs."""
        self.ensure_one()
        products = kept_rfq.order_line.product_id
        # sudo: whoever selects or approves the quote need not be a purchase user.
        other_rfqs = self.sudo().purchase_ids.filtered(
            lambda rfq: rfq != kept_rfq and rfq.state in ('draft', 'sent', 'to approve')
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
