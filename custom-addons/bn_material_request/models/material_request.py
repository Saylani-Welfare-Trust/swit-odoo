from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class MemberApproval(models.Model):

    _name = 'material.request'
    _description = 'Member Approval - Internal Transfer Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Reference', default='New', readonly=True, copy=False, tracking=True)
    
    # Request Details
    user_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True, tracking=True)
    department_id = fields.Many2one(related='user_id.employee_id.department_id', string="Department", store=True)
    purchase_request_id = fields.Many2one('purchase.requisition', string="Purchase Request")
    auto_purchase_request_id = fields.Many2one('purchase.requisition', string="Auto Purchase Request (Stock Shortage)", readonly=True, copy=False, help="Automatically created purchase requisition when stock is insufficient.")
   
    employee_location_id = fields.Many2one(
        'account.analytic.account',
        string='Employee Location',
        related='user_id.employee_id.analytic_account_id',
        readonly=True,
        store=True,
        help='Location (Branch) of the employee who requested the items. Not editable.'
    )
    request_date = fields.Date('Request Date', default=fields.Date.today, readonly=True, tracking=True)
    
    # Source and Destination Locations
    source_location_id = fields.Many2one(
        'stock.location', 
        string='Source Location',
        tracking=True
    )

    source_location_domain = fields.Char(
        compute='_compute_source_location_domain',
        store=False
    )

    allowed_location_ids = fields.Many2many(
        'stock.location',
        related='user_id.allowed_location_ids',
        string='Allowed Locations',
        readonly=True,
        store=False
    )

    # dest_location_domain = fields.Char(
    #     compute='_compute_dest_location_domain',
    #     store=False
    # )

    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        tracking=True
    )

    is_in_budget = fields.Boolean('In Budget', readonly=True, copy=False, tracking=True)
    budget_amount = fields.Float('Available Budget', readonly=True, copy=False)
    
    # Amounts
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary('Total Amount', compute='_compute_total_amount', store=True, currency_field='currency_id')
    
    # Approvals
    cfo_approved = fields.Boolean('CFO Approved', readonly=True, copy=False, tracking=True)
    coo_approved = fields.Boolean('COO Approved', readonly=True, copy=False, tracking=True)
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('technical_validation', 'Technical Validation'),
        ('technical_hod', 'Technical HOD Approval'),
        ('supply_chain', 'Supply Chain Verification'),
        ('on_hold', 'On Hold (Fund Shortage)'),
        ('budget_check', 'Budget Checked'),
        ('hod_approval', 'HOD Approval'),
        # ('cfo_approval', 'CFO Approval'),
        # ('coo_approval', 'COO Approval'),
        ('committee_approval', 'Budget Approval'),
        ('pending', 'Waiting for Delivery'),
        ('done', 'Done'),
        ('purchase_request', 'Purchase Request'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True)

    request_type = fields.Selection([
        ('internal', 'Internal'),
        ('purchase_request', 'Purchase Request'),
    ], string='Request Type', default='internal')
    
    # Picking
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True, copy=False)
    shortage_picking_id = fields.Many2one('stock.picking', string='Shortage Internal Transfer', readonly=True, copy=False)
    
    # Lines
    line_ids = fields.One2many('material.request.line', 'approval_id', string='Products', copy=True)
    
    # Remarks
    rejection_reason = fields.Text('Rejection Reason', tracking=True)
    committee_remarks = fields.Text('Committee Remarks')

    # Technical validation / approval workflow
    technical_validator_id = fields.Many2one(
        'res.users', string='Technical Validator', compute='_compute_technical_approvers',
        store=True, tracking=True,
        help='Manager (HOD) of the requester\'s department. Validates the request technically.')
    technical_hod_id = fields.Many2one(
        'res.users', string='Technical HOD', compute='_compute_technical_approvers',
        store=True, tracking=True,
        help='Head of the technical department that the requested products belong to.')
    resume_state = fields.Char(copy=False, readonly=True)
    hold_reason = fields.Text('Hold Reason', readonly=True, copy=False, tracking=True)
    log_ids = fields.One2many('material.request.log', 'request_id', string='Audit Trail', readonly=True)
    cfo_remarks = fields.Text('CFO Remarks')
    coo_remarks = fields.Text('COO Remarks')


   
    
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request') or 'New'
        return super().create(vals)

    @api.depends('line_ids.subtotal')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(line.subtotal for line in rec.line_ids)



    @api.depends('user_id.allowed_warehouse_ids')
    def _compute_source_location_domain(self):
        for rec in self:
            warehouse_ids = rec.user_id.allowed_warehouse_ids.ids or self.env.user.allowed_warehouse_ids.ids
            
            if warehouse_ids:
                rec.source_location_domain = str([
                    ('warehouse_id', 'in', warehouse_ids),
                    ('complete_name', 'ilike', 'Stock'),
                ])
            else:
                rec.source_location_domain = "[]"



    # @api.depends('user_id.allowed_warehouse_ids')
    # def _compute_source_location_domain(self):
    #     for rec in self:
    #         warehouse_ids = rec.user_id.allowed_warehouse_ids.ids or self.env.user.allowed_warehouse_ids.ids
    #         if warehouse_ids:
    #             rec.source_location_domain = (
    #                 "[('usage','=','internal'),"
    #                 "('warehouse_id','in',%s)]"
    #                 % warehouse_ids
    #             )
    #         else:
    #             rec.source_location_domain = "[('usage','=','internal')]"
    

    @api.depends('department_id.manager_id.user_id', 'line_ids.product_id.categ_id.technical_department_id')
    def _compute_technical_approvers(self):
        for rec in self:
            rec.technical_validator_id = rec.department_id.manager_id.user_id
            hods, missing = rec._get_technical_hods()
            rec.technical_hod_id = hods if len(hods) == 1 and not missing else False

    def _get_technical_hods(self):
        """Return (HOD users, categories without a resolvable HOD) for the request lines."""
        self.ensure_one()
        hods = self.env['res.users']
        missing = self.env['product.category']
        for categ in self.line_ids.product_id.categ_id:
            hod = categ._get_technical_department().manager_id.user_id
            if hod:
                hods |= hod
            else:
                missing |= categ
        return hods, missing

    def _compute_funds(self):
        """Return (available_budget, in_budget) for the request lines."""
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_('Please add at least one product line.'))

        today = fields.Date.today()
        total_available_budget = 0.0
        is_in_budget = True

        for line in self.line_ids:
            analytic = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [line.product_id.id])
            ], limit=1)

            if not analytic:
                raise ValidationError(
                    _('Product "%s" is not linked to any Analytic Account.')
                    % line.product_id.display_name
                )

            budget_lines = self.env['budget.lines'].search([
                ('analytic_account_id', '=', analytic.id),
                ('budget_id', '=', line.budget_id.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ])

            available_budget = sum(abs(l.practical_amount) for l in budget_lines)
            total_available_budget += available_budget

            if line.subtotal > available_budget:
                is_in_budget = False

        return total_available_budget, is_in_budget

    def action_check_budget(self):
        """Preview fund availability without moving the request through the workflow."""
        self.ensure_one()
        total_available_budget, is_in_budget = self._compute_funds()
        self.write({
            'budget_amount': total_available_budget,
            'is_in_budget': is_in_budget,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Budget Check'),
                'message': _('Available budget: %(available)s, required: %(required)s. %(result)s') % {
                    'available': total_available_budget,
                    'required': self.total_amount,
                    'result': _('Funds are sufficient.') if is_in_budget else _('Funds are insufficient.'),
                },
                'type': 'success' if is_in_budget else 'warning',
                'sticky': False,
            },
        }

    def _release_request(self):
        """Funds confirmed and all approvals done: create the transfer / purchase request."""
        self.ensure_one()
        self.budget_amount = max(float(self.budget_amount or 0.0) - float(self.total_amount or 0.0), 0.0)
        if self.request_type == 'internal':
            self._create_internal_transfer()
            self.state = 'pending'
        elif self.request_type == 'purchase_request':
            self._create_purchase_request()
            self.state = 'purchase_request'

    def action_hod_approve(self):
        """HOD approves the request - next step depends on budget status"""
        self.ensure_one()
        if self.state not in ['hod_approval', 'budget_check']:
            raise ValidationError(_('This request is not in HOD Approval state.'))

        if self.department_id and self.department_id.manager_id.id != self.env.user.employee_id.id:
            raise ValidationError(_('This request can only be approved by its respected Manager.'))
        
        

        self._log('hod_approve')
        if self.is_in_budget:
            self._release_request()
        else:
            # Outside budget: go to COO/CFO approval
            self.state = 'committee_approval'

    def action_cfo_approve(self):
        """CFO approves the request"""
        self.ensure_one()
        if self.state != 'committee_approval' or self.cfo_approved:
            raise ValidationError(_('This request is not in Committee Approval state. Or you have validated the entry.'))
        if not self.cfo_remarks:
            raise ValidationError(_('CFO Remarks are required to approve.'))
        self.cfo_approved = True
        self._log('cfo_approve', self.cfo_remarks)
        self._check_committee_approval()
        return True

    def action_coo_approve(self):
        """COO approves the request"""
        self.ensure_one()
        if self.state != 'committee_approval' or self.coo_approved:
            raise ValidationError(_('This request is not in Committee Approval state. Or you have validated the entry.'))
        if not self.coo_remarks:
            raise ValidationError(_('COO Remarks are required to approve.'))
        self.coo_approved = True
        self._log('coo_approve', self.coo_remarks)
        self._check_committee_approval()
        return True

    def _check_committee_approval(self):
        """Check if both CFO and COO have approved"""
        if self.cfo_approved and self.coo_approved:
            # Both approved: go to procurement (simulate with 'done' state and create transfer)
            if self.request_type == 'internal':
                self._create_internal_transfer()
                self.state = 'pending'
            elif self.request_type == 'purchase_request':
                self._create_purchase_request()
                self.state = 'purchase_request'

    # ------------------------------------------------------------------
    # Technical validation / approval workflow
    # ------------------------------------------------------------------
    def _log(self, action, remarks=False):
        self.ensure_one()
        self.env['material.request.log'].sudo().create({
            'request_id': self.id,
            'user_id': self.env.user.id,
            'stage': self.state,
            'action': action,
            'remarks': remarks or False,
        })

    def _assert_state(self, *states):
        self.ensure_one()
        if self.state not in states:
            raise UserError(_('This action is not allowed in the current stage (%s).') % dict(self._fields['state'].selection).get(self.state))

    def _assert_user(self, user_field=None, groups=()):
        self.ensure_one()
        if self.env.is_superuser():
            return
        user = self.env.user
        if user_field and self[user_field] == user:
            return
        if any(user.has_group('bn_material_request.' + g) for g in groups):
            return
        raise UserError(_('You are not authorized to perform this action at the current stage.'))

    def _check_stage_user(self):
        """Only the person/role responsible for the current stage may act on it."""
        self.ensure_one()
        if self.state in ('submitted', 'technical_validation'):
            self._assert_user('technical_validator_id')
        elif self.state == 'technical_hod':
            self._assert_user('technical_hod_id')
        elif self.state == 'supply_chain':
            self._assert_user(groups=('menu_group_material_request_supply_chain',))
        elif self.state == 'on_hold':
            self._assert_user(groups=(
                'menu_group_material_request_cfo',
                'menu_group_material_request_coo',
                'menu_group_material_request_supply_chain',
            ))

    def _advance(self, next_state, action, remarks=False):
        """Log the action, check funds, then move to next_state or put the request on hold.

        next_state 'release' means all approvals are done and the request is fulfilled.
        """
        self.ensure_one()
        self._log(action, remarks)
        available, in_budget = self._compute_funds()
        self.write({'budget_amount': available, 'is_in_budget': in_budget})
        if not in_budget:
            self._put_on_hold(next_state)
        elif next_state == 'release':
            self._release_request()
        else:
            self.state = next_state

    def _put_on_hold(self, resume_state):
        self.ensure_one()
        reason = _('Insufficient funds: required %(required)s, available %(available)s.') % {
            'required': self.total_amount,
            'available': self.budget_amount,
        }
        self._log('hold', reason)
        self.write({'state': 'on_hold', 'resume_state': resume_state, 'hold_reason': reason})

        partners = self.user_id.partner_id | self.technical_validator_id.partner_id | self.technical_hod_id.partner_id
        for group in ('menu_group_material_request_cfo', 'menu_group_material_request_coo', 'menu_group_material_request_supply_chain'):
            partners |= self.env.ref('bn_material_request.' + group).sudo().users.partner_id
        self.message_post(
            body=_('Material Request %(name)s is On Hold due to fund shortage. %(reason)s', name=self.name, reason=reason),
            partner_ids=partners.ids,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_submit(self):
        self.ensure_one()
        self._assert_state('draft')
        if not self.line_ids:
            raise ValidationError(_('Please add at least one product line.'))
        self._compute_technical_approvers()
        if not self.technical_validator_id:
            raise ValidationError(_('The requester\'s department has no manager to act as Technical Validator.'))
        if not self.technical_hod_id:
            hods, missing = self._get_technical_hods()
            if missing:
                raise ValidationError(_(
                    'No Technical HOD found. Set a Technical Department (with a manager) on the product category: %s.'
                ) % ', '.join(missing.mapped('display_name')))
            raise ValidationError(_('The products belong to different technical departments. Please create a separate request for each department.'))
        self._advance('submitted', 'submit')
        return True

    def action_start_validation(self):
        self.ensure_one()
        self._assert_state('submitted')
        self._assert_user('technical_validator_id')
        self._advance('technical_validation', 'start_validation')
        return True

    def _do_validate(self, remarks=False):
        self.ensure_one()
        self._assert_state('technical_validation')
        self._assert_user('technical_validator_id')
        self._advance('technical_hod', 'validate', remarks)

    def _do_hod_approve(self, remarks=False):
        self.ensure_one()
        self._assert_state('technical_hod')
        self._assert_user('technical_hod_id')
        self._advance('supply_chain', 'tech_hod_approve', remarks)

    def _do_verify(self, remarks=False):
        self.ensure_one()
        self._assert_state('supply_chain')
        self._assert_user(groups=('menu_group_material_request_supply_chain',))
        self._advance('release', 'verify', remarks)

    def _do_resume(self, remarks=False):
        self.ensure_one()
        self._assert_state('on_hold')
        self._check_stage_user()
        available, in_budget = self._compute_funds()
        self.write({'budget_amount': available, 'is_in_budget': in_budget})
        if not in_budget:
            raise UserError(_('Funds are still insufficient: required %(required)s, available %(available)s.') % {
                'required': self.total_amount, 'available': available})
        self._log('resume', remarks)
        resume_state = self.resume_state
        self.write({'resume_state': False, 'hold_reason': False})
        if resume_state == 'release':
            self._release_request()
        else:
            self.state = resume_state

    def _do_send_committee(self, remarks=False):
        self.ensure_one()
        self._assert_state('on_hold')
        self._check_stage_user()
        self._log('committee', remarks)
        self.write({
            'state': 'committee_approval',
            'is_in_budget': False,
            'cfo_approved': False,
            'coo_approved': False,
            'resume_state': False,
            'hold_reason': False,
        })

    def _do_reject(self, remarks=False):
        self.ensure_one()
        self.rejection_reason = remarks
        self.action_reject()

    def _create_internal_transfer(self):
        self.ensure_one()

        if not self.source_location_id:
            raise ValidationError(_('Please specify a Source Location.'))
        if not self.dest_location_id:
            raise ValidationError(_('Please specify a Destination Location.'))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not picking_type:
            raise ValidationError(_('No internal transfer picking type found.'))

        move_vals = []
        shortage_move_vals = []
        purchase_lines = []
        stock_info = []

        for line in self.line_ids:
            stock_quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', self.source_location_id.id),
            ])

            available_qty = sum(stock_quant.mapped('available_quantity'))

            stock_info.append({
                'product': line.product_id.display_name,
                'requested': line.quantity,
                'available': available_qty,
            })

            if available_qty >= line.quantity:
                move_vals.append((0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                }))

            elif available_qty > 0:
                move_vals.append((0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'product_uom_qty': available_qty,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                }))

                shortage_qty = line.quantity - available_qty

                purchase_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'product_qty': shortage_qty,
                }))

                shortage_move_vals.append((0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'product_uom_qty': shortage_qty,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                }))

            else:
                purchase_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'product_qty': line.quantity,
                }))

                shortage_move_vals.append((0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.dest_location_id.id,
                }))

        # Create transfer for available stock
        if move_vals:
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.dest_location_id.id,
                'origin': self.name,
                'move_ids_without_package': move_vals,
            })

            self.picking_id = picking.id

        # Create purchase requisition and shortage transfer
        if purchase_lines:
            purchase_request = self.env['purchase.requisition'].create({
                'origin': "%s (Stock Shortage)" % self.name,
                'line_ids': purchase_lines,
                    'material_request_id': self.id,   # <-- autopopulate here
            })

            self.auto_purchase_request_id = purchase_request.id

            shortage_picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.dest_location_id.id,
                'origin': "%s (Stock Shortage)" % self.name,
                'move_ids_without_package': shortage_move_vals,
            })

            self.shortage_picking_id = shortage_picking.id

        if not move_vals and not purchase_lines:
            raise ValidationError(
                _('No products to transfer or purchase.')
            )

        return self.picking_id
    
    def _create_purchase_request(self):
        """Create a purchase request (purchase.requisition) for the approved request"""
        self.ensure_one()

        # Create purchase line
        line_vals = []
        for line in self.line_ids:
            line_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'product_qty': line.quantity,
            }))
        # Create picking
        purchase_request = self.env['purchase.requisition'].create({
            'origin': self.name,
            'line_ids': line_vals,
            'material_request_id': self.id,   # <-- autopopulate here
        })
        # Confirm and assign purchase
        self.purchase_request_id = purchase_request.id
        return purchase_request

    def action_reject(self):
        """Reject the request"""
        self.ensure_one()

        if not self.rejection_reason:
            raise ValidationError(_('Please provide a rejection reason.'))
        if self.state in ('done', 'rejected', 'pending', 'purchase_request'):
            raise UserError(_('This request can no longer be rejected.'))
        self._check_stage_user()

        self.picking_id.action_cancel()
        self._log('reject', self.rejection_reason)
        self.write({'state': 'rejected', 'resume_state': False})
        return True

    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.ensure_one()

        self._log('reset')
        self.write({
            'state': 'draft',
            'is_in_budget': False,
            'budget_amount': 0.0,
            'cfo_approved': False,
            'coo_approved': False,
            'rejection_reason': False,
            'resume_state': False,
            'hold_reason': False,
        })

        return True

    def action_view_picking(self):
        """View the created internal transfer"""
        self.ensure_one()
        
        if not self.picking_id:
            raise ValidationError(_('No internal transfer found.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    def action_view_shortage_picking(self):
        """View the created shortage internal transfer"""
        self.ensure_one()
        if not self.shortage_picking_id:
            raise ValidationError(_('No shortage internal transfer found.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shortage Internal Transfer'),
            'res_model': 'stock.picking',
            'res_id': self.shortage_picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }  
    def action_view_purchase_request(self):
        """View the created purchase request"""
        self.ensure_one()
        
        if not self.purchase_request_id:
            raise ValidationError(_('No Purchase Request found.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'purchase.requisition',
            'res_id': self.purchase_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_auto_purchase_request(self):
        """View the auto-created purchase request (due to stock shortage)"""
        self.ensure_one()
        
        if not self.auto_purchase_request_id:
            raise ValidationError(_('No Auto Purchase Request found.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Auto Purchase Request (Stock Shortage)'),
            'res_model': 'purchase.requisition',
            'res_id': self.auto_purchase_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # def action_committee_approve(self):
    #     if self.state != 'hod_approval':
    #         raise ValidationError(_('This request is not in HOD Approval state.'))
        
    #     self.state = 'committee_approval'
