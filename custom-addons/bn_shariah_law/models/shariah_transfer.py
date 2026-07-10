from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class ShariahTransfer(models.Model):
    _name = 'shariah.transfer'
    _description = 'Shariah Fund Transfer'
    _order = 'date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default=lambda self: _('New'), required=True, copy=False)
    date = fields.Date(string='Transfer Date', required=True, default=fields.Date.context_today)
    source_analytic_account_id = fields.Many2one('account.analytic.account', string='Source Account', required=True)
    destination_analytic_account_id = fields.Many2one('account.analytic.account', string='Destination Account', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    shariah_law_person_id = fields.Many2one(
        'shariah.law.person', 
        string='Shariah Law Person',
        help='Select the Shariah Law Person responsible for this transfer'
    )
    note = fields.Text(string='Notes')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('member_approval', 'Member Approval'),
        ('posted', 'Posted'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    member_posted = fields.Boolean(string='Member Posted', default=False, tracking=True)
    is_sync_shariah_law = fields.Boolean(string='Synced with Shariah Law', default=False)
    
    # Approval fields
    member_approval_date = fields.Datetime(string='Member Approval Date', readonly=True)
    member_approval_user_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    
    # Rule information
    rule_id = fields.Many2one('segment.transfer.rule', string='Transfer Rule', readonly=True)
    requires_approval = fields.Boolean(string='Requires Approval', compute='_compute_approval_info', store=False)

    @api.depends('source_analytic_account_id', 'destination_analytic_account_id', 'amount')
    def _compute_approval_info(self):
        """Compute if transfer requires approval based on rules."""
        for rec in self:
            rec.requires_approval = False
            if rec.source_analytic_account_id and rec.destination_analytic_account_id and rec.amount:
                try:
                    rule = self.env['segment.transfer.rule'].check_transfer_allowed(
                        rec.source_analytic_account_id.id,
                        rec.destination_analytic_account_id.id,
                        rec.amount
                    )
                    rec.requires_approval = rule.requires_approval
                    rec.rule_id = rule.id
                except:
                    pass

    @api.onchange('source_analytic_account_id', 'destination_analytic_account_id', 'amount')
    def _onchange_check_approval(self):
        """Check if approval is required and update fields."""
        if self.source_analytic_account_id and self.destination_analytic_account_id and self.amount:
            try:
                rule = self.env['segment.transfer.rule'].check_transfer_allowed(
                    self.source_analytic_account_id.id,
                    self.destination_analytic_account_id.id,
                    self.amount
                )
                if rule.requires_approval:
                    return {
                        'warning': {
                            'title': _('Approval Required'),
                            'message': _(
                                'This transfer requires member approval. '
                                'Please make sure to select a Shariah Law Person and get member approval '
                                'before posting.'
                            ),
                        }
                    }
            except:
                pass

    @api.constrains('shariah_law_person_id', 'requires_approval', 'member_posted')
    def _check_approval_requirements(self):
        """Validate that if approval is required, shariah_law_person is set and member_posted is True."""
        for rec in self:
            if rec.requires_approval and rec.state == 'posted':
                if not rec.shariah_law_person_id:
                    raise ValidationError(_(
                        'Shariah Law Person is required for this transfer as it requires approval.'
                    ))
                if not rec.member_posted:
                    raise ValidationError(_(
                        'This transfer requires member approval. Please click "Member Post" button first.'
                    ))

    def action_post(self):
        """Post the transfer: update daily balances and shariah law instantly."""
        for rec in self:
            if rec.state == 'posted':
                continue
            
            # Check if member approval is required and not yet approved
            if rec.requires_approval and not rec.member_posted:
                rec.state = 'member_approval'
                rec.message_post(body=_("Transfer requires member approval. Sent for approval."))
                continue
            
            # Check if shariah law person is selected when approval is required
            if rec.requires_approval and not rec.shariah_law_person_id:
                raise UserError(_('Shariah Law Person is required for this transfer.'))
            
            if rec.destination_analytic_account_id.member_approval and not rec.member_posted:
                raise UserError(_('Need member approval first.'))

            today = rec.date
            
            # === 1. UPDATE DAILY BALANCES ===
            daily_source = self._get_or_create_daily_balance(rec.source_analytic_account_id.id, today)
            daily_source.write({'transfer': daily_source.transfer - rec.amount})  # NEGATIVE for out
            
            daily_dest = self._get_or_create_daily_balance(rec.destination_analytic_account_id.id, today)
            daily_dest.write({'transfer': daily_dest.transfer + rec.amount})  # POSITIVE for in
            
            # Recompute balances for both accounts
            self._recompute_daily_balances([daily_source, daily_dest])
            
            # === 2. UPDATE SHARIAH LAW INSTANTLY WITH HIERARCHY ===
            config = self.env['shariah.law.config'].get_config()
            if config.enable_transfer_sync:
                self._sync_transfer_to_shariah_law(rec)
            
            # === 3. MARK AS SYNCED ===
            rec.is_sync_shariah_law = True
            rec.state = 'posted'
            
            rec.message_post(body=_("Transfer posted successfully."))

    def action_member_post(self):
        """Member approval for transfer."""
        for rec in self:
            # Check if shariah law person is selected
            if rec.requires_approval and not rec.shariah_law_person_id:
                raise UserError(_('Please select a Shariah Law Person before member posting.'))
            
            # Check if transfer requires approval
            if not rec.requires_approval:
                raise UserError(_('This transfer does not require member approval.'))
            
            if rec.state == 'posted':
                raise UserError(_('This transfer is already posted.'))
            
            # Check if user has permission to approve
            if not self._check_approval_permission(rec):
                raise UserError(_('You do not have permission to approve this transfer.'))
            
            # Approve the transfer
            rec.member_posted = True
            rec.member_approval_date = fields.Datetime.now()
            rec.member_approval_user_id = self.env.user.id
            
            rec.message_post(body=_("Transfer approved by %s.") % self.env.user.name)
            
            # If state is member_approval, post it automatically
            if rec.state == 'member_approval':
                rec.action_post()

    def action_reject(self):
        """Reject the transfer."""
        for rec in self:
            if rec.state != 'member_approval':
                raise UserError(_('This transfer is not waiting for member approval.'))
            
            if not rec.rejection_reason:
                raise UserError(_('Please provide a reason for rejection.'))
            
            rec.state = 'rejected'
            rec.message_post(body=_("Transfer rejected by %s. Reason: %s") % (
                self.env.user.name, rec.rejection_reason
            ))

    def _check_approval_permission(self, transfer):
        """Check if current user has permission to approve."""
        # Check if user is in approval group
        if transfer.rule_id and transfer.rule_id.approval_group_id:
            return self.env.user.has_group(transfer.rule_id.approval_group_id.id)
        
        # Check if user has manager rights
        return self.env.user.has_group('shariah_law.group_shariah_law_manager_group')

    def action_send_for_approval(self):
        """Send transfer for member approval."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft transfers can be sent for approval.'))
            
            # Check if shariah law person is selected
            if rec.requires_approval and not rec.shariah_law_person_id:
                raise UserError(_('Please select a Shariah Law Person before sending for approval.'))
            
            if rec.requires_approval:
                rec.state = 'member_approval'
                rec.message_post(body=_("Transfer sent for member approval."))
            else:
                raise UserError(_('This transfer does not require approval. You can post it directly.'))

    def _sync_transfer_to_shariah_law(self, transfer):
        """
        Instantly sync transfer to shariah.law with hierarchy support.
        Transfer Out = NEGATIVE, Transfer In = POSITIVE
        """
        shariah_obj = self.env['shariah.law']
        
        # Source account - Transfer OUT (NEGATIVE)
        if transfer.source_analytic_account_id:
            self._update_shariah_law_with_hierarchy(
                shariah_obj,
                transfer.source_analytic_account_id,
                -transfer.amount  # NEGATIVE for out
            )
        
        # Destination account - Transfer IN (POSITIVE)
        if transfer.destination_analytic_account_id:
            self._update_shariah_law_with_hierarchy(
                shariah_obj,
                transfer.destination_analytic_account_id,
                transfer.amount  # POSITIVE for in
            )

    def _update_shariah_law_with_hierarchy(self, shariah_obj, account, amount):
        """
        Update shariah law record for an analytic account and all its parents.
        """
        if not account or not amount:
            return
        
        today = fields.Date.context_today(self)
        
        # Get or create today's shariah law record for this account
        shariah_law = self._get_or_create_today_shariah_record(shariah_obj, account, today)
        
        # Update transfer amount
        if shariah_law:
            current_transfer = shariah_law.transfer_amount or 0.0
            shariah_law.write({
                'transfer_amount': current_transfer + amount
            })
        
        # Recursively update parent accounts
        if account.parent_id:
            self._update_shariah_law_with_hierarchy(shariah_obj, account.parent_id, amount)

    def _get_or_create_today_shariah_record(self, shariah_obj, account, today):
        """
        Get or create today's shariah.law record for an analytic account.
        Creates hierarchy chain if parents don't exist.
        """
        if not account:
            return False
        
        # Check if today's record exists
        shariah_law = shariah_obj.search([
            ('analytic_account_id', '=', account.id),
            ('date', '=', today)
        ], limit=1)
        
        if not shariah_law:
            # Ensure parent records exist first
            if account.parent_id:
                self._get_or_create_today_shariah_record(shariah_obj, account.parent_id, today)
            
            # Get yesterday's closing balance
            yesterday = today - timedelta(days=1)
            yesterday_record = shariah_obj.search([
                ('analytic_account_id', '=', account.id),
                ('date', '=', yesterday)
            ], limit=1)
            
            opening_balance = yesterday_record.closing_balance if yesterday_record else 0.0
            
            # Create today's shariah law record
            shariah_law = shariah_obj.create({
                'parent_id': account.parent_id.id if account.parent_id else False,
                'analytic_account_id': account.id,
                'date': today,
                'opening_balance': opening_balance,
                'pos_donation_amount': 0.0,
                'api_donation_amount': 0.0,
                'dik_amount': 0.0,
                'po_amount': 0.0,
                'welfare_amount': 0.0,
                'microfinance_amount': 0.0,
                'expense_amount': 0.0,
                'transfer_amount': 0.0,
            })
        
        return shariah_law

    def _get_or_create_daily_balance(self, analytic_account_id, date):
        """Get or create daily balance record."""
        daily = self.env['shariah.daily.balance'].search([
            ('analytic_account_id', '=', analytic_account_id),
            ('date', '=', date)
        ], limit=1)
        
        if not daily:
            daily = self.env['shariah.daily.balance'].create({
                'analytic_account_id': analytic_account_id,
                'date': date,
            })
        
        return daily

    def _recompute_daily_balances(self, daily_records):
        """Recompute balances for daily records."""
        for daily in daily_records:
            daily._compute_balances()
            daily._compute_total_donation()

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('shariah.transfer') or _('New')
        return super().create(vals)

    def write(self, vals):
        """Handle state change to posted."""
        result = super().write(vals)
        
        # If state changed to posted and not synced, sync immediately
        if 'state' in vals and vals['state'] == 'posted':
            for rec in self:
                if not rec.is_sync_shariah_law:
                    rec.action_post()
        
        return result