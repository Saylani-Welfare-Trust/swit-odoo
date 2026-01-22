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
        required=True,
        domain=[('usage', '=', 'internal')],
        tracking=True
    )
    
    dest_location_domain = fields.Char(
        compute='_compute_dest_location_domain'
    )

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
        ('budget_check', 'Budget Checked'),
        ('hod_approval', 'HOD Approval'),
        # ('cfo_approval', 'CFO Approval'),
        # ('coo_approval', 'COO Approval'),
        ('committee_approval', 'Committee Approval'),
        ('done', 'Done'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True)
    
    # Picking
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True, copy=False)
    
    # Lines
    line_ids = fields.One2many('material.request.line', 'approval_id', string='Products', copy=True)
    
    # Remarks
    rejection_reason = fields.Text('Rejection Reason', tracking=True)
    committee_remarks = fields.Text('Committee Remarks')
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



    @api.depends('employee_location_id')
    def _compute_dest_location_domain(self):
        for rec in self:
            if rec.employee_location_id:
                rec.dest_location_domain = (
                    "[('usage','=','internal'),"
                    "('analytic_account_id','=',%d)]"
                    % rec.employee_location_id.id
                )
            else:
                rec.dest_location_domain = "[('usage','=','internal')]"

    def action_check_budget(self):
        """Check budget per analytic account (supports multiple lines)"""
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_('Please add at least one product line.'))

        today = fields.Date.today()

        # Budget check per line (analytic + budget)
        total_available_budget = 0.0
        is_in_budget = True
        # STEP 1: Build analytic-wise totals
        # ----------------------------------------
        analytic_amount_map = {}  # {analytic_account: total_amount}

        for line in self.line_ids:
            analytic_line = self.env['analytical.product.line'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if not analytic_line or not analytic_line.analytic_account_id:
                raise ValidationError(
                    _('Product "%s" is not linked to any Analytic Account.')
                    % line.product_id.display_name
                )

            analytic = analytic_line.analytic_account_id

            budget = line.budget_id
            if not budget:
                raise ValidationError(_('Please select a Budgetary Position for product "%s".') % line.product_id.display_name)
            budget_lines = self.env['budget.lines'].search([
                ('analytic_account_id', '=', analytic.id),
                ('budget_id', '=', budget.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ])
            if not budget_lines:
                raise ValidationError(_('No active budget found for Analytic Account: %s and Budget: %s') % (analytic.display_name, budget.display_name))
            available_budget = sum(
                l.planned_amount - abs(l.practical_amount)
                for l in budget_lines
            )
            total_available_budget += available_budget
            if line.subtotal > available_budget:
                is_in_budget = False

        # Set state for approval cycle
        next_state = 'hod_approval' if is_in_budget else 'committee_approval'
        self.write({
            'budget_amount': total_available_budget,
            'is_in_budget': is_in_budget,
            'state': next_state,
        })
        return True

    def action_hod_approve(self):
        """HOD approves the request - next step depends on budget status"""
        self.ensure_one()
        if self.state not in ['hod_approval', 'budget_check']:
            raise ValidationError(_('This request is not in HOD Approval state.'))

        if self.department_id and self.department_id.manager_id.id != self.env.user.employee_id.id:
            raise ValidationError(_('This request can only be approved by its respected Manager.'))

        if self.is_in_budget:
            # Within budget: go to procurement (simulate with 'done' state and create transfer)
            self._create_internal_transfer()
            self.state = 'done'
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
        self._check_committee_approval()
        return True

    def _check_committee_approval(self):
        """Check if both CFO and COO have approved"""
        if self.cfo_approved and self.coo_approved:
            # Both approved: go to procurement (simulate with 'done' state and create transfer)
            self._create_internal_transfer()
            self.state = 'done'

    def _create_internal_transfer(self):
        """Create an internal transfer (stock.picking) for the approved request"""
        self.ensure_one()
        # Get internal transfer picking type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise ValidationError(_('No internal transfer picking type found.'))
        # Create stock moves
        move_vals = []
        for line in self.line_ids:
            move_vals.append((0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.dest_location_id.id,
            }))
        # Create picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': self.name,
            'move_ids_without_package': move_vals,
        })
        # Confirm and assign picking
        picking.action_confirm()
        picking.action_assign()
        self.picking_id = picking.id
        # Subscribe to picking done event by overriding write on picking (monkey patch or via automated action), or add a method to be called from picking when validated
        return picking

    def action_reject(self):
        """Reject the request"""
        self.ensure_one()
        
        if not self.rejection_reason:
            raise ValidationError(_('Please provide a rejection reason.'))
        
        self.picking_id.action_cancel()

        self.state = 'rejected'
        
        return True

    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.ensure_one()
        
        self.write({
            'state': 'draft',
            'is_in_budget': False,
            'budget_amount': 0.0,
            'cfo_approved': False,
            'coo_approved': False,
            'rejection_reason': False,
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

    # def action_committee_approve(self):
    #     if self.state != 'hod_approval':
    #         raise ValidationError(_('This request is not in HOD Approval state.'))
        
    #     self.state = 'committee_approval'
