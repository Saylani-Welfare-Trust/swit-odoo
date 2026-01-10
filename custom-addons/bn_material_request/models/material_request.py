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
    request_date = fields.Date('Request Date', default=fields.Date.today, readonly=True, tracking=True)
    
    # Source and Destination Locations
    source_location_id = fields.Many2one(
        'stock.location', 
        string='Source Location', 
        required=True,
        domain=[('usage', '=', 'internal')],
        tracking=True
    )
    dest_location_id = fields.Many2one(
        'stock.location', 
        string='Destination Location', 
        required=True,
        domain=[('usage', '=', 'internal')],
        tracking=True
    )
    
    # Budget Related
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 
        string='Analytic Account',
        help='Analytic account for budget checking',
        tracking=True
    )
    budget_position_id = fields.Many2one(
        'account.budget.post',
        string='Budgetary Position',
        help='Budgetary position to check against',
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
        ('committee_approval', 'Committee Approval'),
        ('done', 'Done'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True)
    
    # Picking
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True, copy=False)
    
    # Lines
    line_ids = fields.One2many('material.request.line', 'approval_id', string='Products', copy=True)
    
    # Remarks
    remarks = fields.Text('Remarks', tracking=True)
    rejection_reason = fields.Text('Rejection Reason', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request') or 'New'
        return super().create(vals)

    @api.depends('line_ids.subtotal')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(line.subtotal for line in rec.line_ids)

    def action_check_budget(self):
        """Check if the request is within budget"""
        self.ensure_one()
        
        if not self.line_ids:
            raise ValidationError(_('Please add at least one product line.'))
        
        # Check budget availability
        available_budget = 0.0
        is_in_budget = False
        
        if self.analytic_account_id and self.budget_position_id:
            # Search for active budget lines
            budget_lines = self.env['budget.lines'].search([
                ('analytic_account_id', '=', self.analytic_account_id.id),
                ('general_budget_id', '=', self.budget_position_id.id),
                ('date_from', '<=', fields.Date.today()),
                ('date_to', '>=', fields.Date.today()),
                # ('budget_id.state', '=', 'validate'),
            ])
            
            if budget_lines:
                # Calculate remaining budget (planned - practical)
                for line in budget_lines:
                    available_budget += line.planned_amount - abs(line.practical_amount)
                
                # Check if total amount is within budget
                is_in_budget = self.total_amount <= available_budget
        
        self.write({
            'budget_amount': available_budget,
            'is_in_budget': is_in_budget,
            'state': 'budget_check',
        })
        # raise UserError(str(available_budget))
        
        # Auto-transition based on budget check
        if is_in_budget:
            self.state = 'hod_approval'
        else:
            self.state = 'committee_approval'
        
        return True

    def action_hod_approve(self):
        """HOD approves the request - creates internal transfer"""
        self.ensure_one()
        if self.state != 'hod_approval':
            raise ValidationError(_('This request is not in HOD Approval state.'))
        # Create internal transfer
        self._create_internal_transfer()
        # Do not set state to done here; will be set when picking is validated
        return True

    def action_cfo_approve(self):
        """CFO approves the request"""
        self.ensure_one()
        
        if self.state != 'committee_approval':
            raise ValidationError(_('This request is not in Committee Approval state.'))
        
        self.cfo_approved = True
        self._check_committee_approval()
        
        return True

    def action_coo_approve(self):
        """COO approves the request"""
        self.ensure_one()
        
        if self.state != 'committee_approval':
            raise ValidationError(_('This request is not in Committee Approval state.'))
        
        self.coo_approved = True
        self._check_committee_approval()
        
        return True

    def _check_committee_approval(self):
        """Check if both CFO and COO have approved"""
        if self.cfo_approved and self.coo_approved:
            # Create internal transfer
            self._create_internal_transfer()
            # Do not set state to done here; will be set when picking is validated

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



