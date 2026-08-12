from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

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
    
    # Display fields
    source_current_balance = fields.Monetary(
        string='Source Current Balance',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )
    destination_current_balance = fields.Monetary(
        string='Destination Current Balance',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )
    source_balance_after = fields.Monetary(
        string='Source Balance After Transfer',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )
    destination_balance_after = fields.Monetary(
        string='Destination Balance After Transfer',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

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
                        rec.amount or 0.0
                    )
                    rec.rule_id = rule.id
                    rec.transfer_allowed = rule.allowed
                    rec.max_transfer_amount = rule.max_transfer_amount
                    rec.rule_notes = rule.notes
                    rec.requires_approval = rule.requires_approval
                except ValidationError:
                    rec.transfer_allowed = False
                    rec.rule_id = False

    @api.depends('source_analytic_account_id', 'destination_analytic_account_id', 'amount')
    def _compute_balances(self):
        """Compute current balances and balance after transfer."""
        today = fields.Date.context_today(self)
        
        for rec in self:
            rec.source_current_balance = 0.0
            rec.destination_current_balance = 0.0
            rec.source_balance_after = 0.0
            rec.destination_balance_after = 0.0
            
            # Get source current balance
            if rec.source_analytic_account_id:
                daily_balance = self.env['shariah.daily.balance'].search([
                    ('analytic_account_id', '=', rec.source_analytic_account_id.id),
                    ('date', '=', today)
                ], limit=1)
                
                if daily_balance:
                    rec.source_current_balance = daily_balance.closing_balance
                else:
                    # Get from shariah.law if daily balance doesn't exist
                    shariah_law = self.env['shariah.law'].search([
                        ('analytic_account_id', '=', rec.source_analytic_account_id.id),
                        ('date', '=', today)
                    ], limit=1)
                    rec.source_current_balance = shariah_law.closing_balance if shariah_law else 0.0
            
            # Get destination current balance
            if rec.destination_analytic_account_id:
                daily_balance = self.env['shariah.daily.balance'].search([
                    ('analytic_account_id', '=', rec.destination_analytic_account_id.id),
                    ('date', '=', today)
                ], limit=1)
                
                if daily_balance:
                    rec.destination_current_balance = daily_balance.closing_balance
                else:
                    shariah_law = self.env['shariah.law'].search([
                        ('analytic_account_id', '=', rec.destination_analytic_account_id.id),
                        ('date', '=', today)
                    ], limit=1)
                    rec.destination_current_balance = shariah_law.closing_balance if shariah_law else 0.0
            
            # Calculate balances after transfer
            if rec.amount > 0:
                rec.source_balance_after = rec.source_current_balance - rec.amount
                rec.destination_balance_after = rec.destination_current_balance + rec.amount

    @api.onchange('source_analytic_account_id')
    def _onchange_source_analytic_account_id(self):
        """Clear destination and update allowed destinations when source changes."""
        self.destination_analytic_account_id = False
        self._compute_allowed_destinations()
        self._compute_balances()

    @api.onchange('destination_analytic_account_id')
    def _onchange_destination_analytic_account_id(self):
        """Update rule info when destination changes."""
        self._compute_rule_info()
        self._compute_balances()

    @api.onchange('amount')
    def _onchange_amount(self):
        """Check amount against max limit and update balances."""
        if self.amount > 0 and self.source_analytic_account_id and self.destination_analytic_account_id:
            try:
                self.env['segment.transfer.rule'].check_transfer_allowed(
                    self.source_analytic_account_id.id,
                    self.destination_analytic_account_id.id,
                    self.amount
                )
                self._compute_balances()
            except ValidationError as e:
                return {
                    'warning': {
                        'title': _('Transfer Limit Exceeded'),
                        'message': str(e),
                    }
                }
        elif self.amount > 0:
            self._compute_balances()

    def action_create_transfer(self):
        """Create and post the transfer."""
        self.ensure_one()
        
        # Validate segments
        if self.source_analytic_account_id == self.destination_analytic_account_id:
            raise UserError(_('Source and destination accounts must be different.'))
        
        # Check if amount is positive
        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))
        
        # Check if destination is in allowed list
        if self.destination_analytic_account_id not in self.allowed_destination_ids:
            raise UserError(_(
                "Transfer from '%s' to '%s' is not allowed.\n"
                "Please configure this destination in the transfer rules."
            ) % (self.source_analytic_account_id.name, self.destination_analytic_account_id.name))
        
        # Check if source has enough balance
        if self.source_current_balance < self.amount:
            raise UserError(_(
                "Insufficient balance in source account.\n"
                "Current balance: %s\n"
                "Transfer amount: %s"
            ) % (self.source_current_balance, self.amount))
        
        # Check transfer rules and get rule
        rule = None
        try:
            rule = self.env['segment.transfer.rule'].check_transfer_allowed(
                self.source_analytic_account_id.id,
                self.destination_analytic_account_id.id,
                self.amount
            )
        except ValidationError as e:
            raise UserError(str(e))
        
        # Create the transfer
        transfer_vals = {
            'date': self.date,
            'source_analytic_account_id': self.source_analytic_account_id.id,
            'destination_analytic_account_id': self.destination_analytic_account_id.id,
            'amount': self.amount,
            'note': self.note,
            'state': 'draft',
            'requires_approval': rule.requires_approval if rule else False,
            'rule_id': rule.id if rule else False,
        }
        
        # Create the transfer
        transfer = self.env['shariah.transfer'].create(transfer_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer',
            'res_id': transfer.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Transfer'),
        }