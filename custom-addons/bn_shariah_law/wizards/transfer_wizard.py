from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ShariahTransferWizard(models.TransientModel):
    _name = 'shariah.transfer.wizard'
    _description = 'Transfer Funds Wizard'

    source_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Source Account',
        required=True,
        domain="[('plan_id.name', '=', 'Segment')]"
    )
    
    destination_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Destination Account',
        required=True,
        domain="[('plan_id.name', '=', 'Segment')]"
    )
    
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    date = fields.Date(string='Transfer Date', required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    note = fields.Text(string='Notes')
    
    # Computed fields for rule information
    rule_id = fields.Many2one('segment.transfer.rule', string='Transfer Rule', readonly=True)
    transfer_allowed = fields.Boolean(string='Transfer Allowed', compute='_compute_rule_info', store=False)
    max_transfer_amount = fields.Monetary(string='Max Allowed Amount', compute='_compute_rule_info', store=False)
    rule_notes = fields.Text(string='Rule Notes', compute='_compute_rule_info', store=False)
    requires_approval = fields.Boolean(string='Requires Approval', compute='_compute_rule_info', store=False)
    
    # Allowed destinations for the selected source
    allowed_destination_ids = fields.Many2many(
        'account.analytic.account',
        compute='_compute_allowed_destinations',
        store=False
    )
    allowed_dest_count = fields.Integer(string='Allowed Destinations', compute='_compute_rule_info', store=False)

    @api.depends('source_analytic_account_id')
    def _compute_allowed_destinations(self):
        """Compute allowed destinations for the selected source."""
        for rec in self:
            if rec.source_analytic_account_id:
                rec.allowed_destination_ids = self.env['segment.transfer.rule'].get_allowed_destinations(
                    rec.source_analytic_account_id.id
                )
                # If current destination is not allowed, clear it
                if rec.destination_analytic_account_id and rec.destination_analytic_account_id not in rec.allowed_destination_ids:
                    rec.destination_analytic_account_id = False
            else:
                rec.allowed_destination_ids = False

    @api.depends('source_analytic_account_id', 'destination_analytic_account_id', 'amount')
    def _compute_rule_info(self):
        """Compute rule information for display."""
        for rec in self:
            rec.transfer_allowed = False
            rec.max_transfer_amount = 0.0
            rec.rule_notes = ''
            rec.requires_approval = False
            rec.rule_id = False
            rec.allowed_dest_count = 0
            
            if rec.source_analytic_account_id:
                # Get allowed destinations count
                allowed_dests = self.env['segment.transfer.rule'].get_allowed_destinations(
                    rec.source_analytic_account_id.id
                )
                rec.allowed_dest_count = len(allowed_dests)
            
            if rec.source_analytic_account_id and rec.destination_analytic_account_id:
                try:
                    rule = self.env['segment.transfer.rule'].check_transfer_allowed(
                        rec.source_analytic_account_id.id,
                        rec.destination_analytic_account_id.id,
                        rec.amount
                    )
                    rec.rule_id = rule.id
                    rec.transfer_allowed = rule.allowed
                    rec.max_transfer_amount = rule.max_transfer_amount
                    rec.rule_notes = rule.notes
                    rec.requires_approval = rule.requires_approval
                except ValidationError:
                    rec.transfer_allowed = False
                    rec.rule_id = False

    @api.onchange('source_analytic_account_id')
    def _onchange_source_analytic_account_id(self):
        """Clear destination and update allowed destinations when source changes."""
        self.destination_analytic_account_id = False
        self._compute_allowed_destinations()

    @api.onchange('amount')
    def _onchange_amount(self):
        """Check amount against max limit."""
        if self.amount > 0 and self.source_analytic_account_id and self.destination_analytic_account_id:
            try:
                self.env['segment.transfer.rule'].check_transfer_allowed(
                    self.source_analytic_account_id.id,
                    self.destination_analytic_account_id.id,
                    self.amount
                )
            except ValidationError as e:
                return {
                    'warning': {
                        'title': _('Transfer Limit Exceeded'),
                        'message': str(e),
                    }
                }

    def action_create_transfer(self):
        """Create and post the transfer."""
        self.ensure_one()
        
        # Validate segments
        if self.source_analytic_account_id == self.destination_analytic_account_id:
            raise UserError(_('Source and destination accounts must be different.'))
        
        # Check if destination is in allowed list
        if self.destination_analytic_account_id not in self.allowed_destination_ids:
            raise UserError(_(
                "Transfer from '%s' to '%s' is not allowed.\n"
                "Please configure this destination in the transfer rules."
            ) % (self.source_analytic_account_id.name, self.destination_analytic_account_id.name))
        
        # Check transfer rules and get rule
        try:
            rule = self.env['segment.transfer.rule'].check_transfer_allowed(
                self.source_analytic_account_id.id,
                self.destination_analytic_account_id.id,
                self.amount
            )
            
            # Check if approval is required
            if rule.requires_approval:
                # Check if user is in approval group
                user_has_approval = False
                if rule.approval_group_id:
                    user_has_approval = self.env.user.has_group(rule.approval_group_id.id)
                
                if not user_has_approval:
                    # Create transfer with pending approval state
                    transfer = self.env['shariah.transfer'].create({
                        'date': self.date,
                        'source_analytic_account_id': self.source_analytic_account_id.id,
                        'destination_analytic_account_id': self.destination_analytic_account_id.id,
                        'amount': self.amount,
                        'note': f"{self.note or ''}\n[Pending Approval]",
                        'state': 'draft',
                        'requires_approval': True,
                    })
                    
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'shariah.transfer',
                        'res_id': transfer.id,
                        'view_mode': 'form',
                        'target': 'current',
                        'name': _('Transfer (Pending Approval)'),
                    }
                    
        except ValidationError as e:
            raise UserError(str(e))
        
        # Create the transfer
        transfer = self.env['shariah.transfer'].create({
            'date': self.date,
            'source_analytic_account_id': self.source_analytic_account_id.id,
            'destination_analytic_account_id': self.destination_analytic_account_id.id,
            'amount': self.amount,
            'note': self.note,
            'state': 'draft',
            'requires_approval': rule.requires_approval if rule else False,
        })
        
        # Post the transfer (this triggers instant sync)
        transfer.action_post()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer',
            'res_id': transfer.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Transfer'),
        }

    @api.model
    def default_get(self, fields_list):
        """Set default source segment from context if provided."""
        defaults = super().default_get(fields_list)
        context = self.env.context
        
        if context.get('default_source_segment_id'):
            defaults['source_analytic_account_id'] = context['default_source_segment_id']
        
        return defaults