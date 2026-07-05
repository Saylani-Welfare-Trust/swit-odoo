from odoo import api, fields, models, _
from odoo.exceptions import UserError
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
    note = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', tracking=True)

    member_posted = fields.Boolean(string='Member Posted', default=False, tracking=True)
    is_sync_shariah_law = fields.Boolean(string='Synced with Shariah Law', default=False)

    
    def action_post(self):
        """Post the transfer: update daily balances and shariah law instantly."""
        for rec in self:
            if rec.state == 'posted':
                continue
            if rec.destination_analytic_account_id.member_approval and not rec.member_posted:
                raise UserError(_('Need member approval first.'))

            today = rec.date
            
            # === 1. UPDATE DAILY BALANCES ===
            daily_source = self._get_or_create_daily_balance(rec.source_analytic_account_id.id, today)
            daily_source.write({'transfer_out': daily_source.transfer_out + rec.amount})
            
            daily_dest = self._get_or_create_daily_balance(rec.destination_analytic_account_id.id, today)
            daily_dest.write({'transfer_in': daily_dest.transfer_in + rec.amount})
            
            # Recompute balances for both accounts
            self._recompute_daily_balances([daily_source, daily_dest])
            
            # === 2. UPDATE SHARIAH LAW INSTANTLY ===
            config = self.env['shariah.law.config'].get_config()
            if config.enable_instant_transfer_sync:
                self._sync_transfer_to_shariah_law(rec)
            
            # === 3. MARK AS SYNCED ===
            rec.is_sync_shariah_law = True
            rec.state = 'posted'

    def _sync_transfer_to_shariah_law(self, transfer):
        """Instantly sync transfer to shariah.law."""
        shariah_obj = self.env['shariah.law']
        
        # Source account - Transfer OUT
        if transfer.source_analytic_account_id:
            self._update_shariah_law_amount(
                shariah_obj,
                transfer.source_analytic_account_id.id,
                'transfer_out_amount',
                transfer.amount
            )
        
        # Destination account - Transfer IN
        if transfer.destination_analytic_account_id:
            self._update_shariah_law_amount(
                shariah_obj,
                transfer.destination_analytic_account_id.id,
                'transfer_in_amount',
                transfer.amount
            )

    def _update_shariah_law_amount(self, shariah_obj, analytic_account_id, field_name, amount):
        """Update shariah law record for an analytic account."""
        shariah_law = shariah_obj.search([
            ('analytic_account_id', '=', analytic_account_id)
        ], limit=1)
        
        account = self.env['account.analytic.account'].browse(analytic_account_id)
        if not account.exists():
            return
        
        if not shariah_law:
            # Create new shariah law record
            shariah_law = shariah_obj.create({
                'parent_id': account.parent_id.id if account.parent_id else False,
                'analytic_account_id': account.id,
                'pos_donation_amount': 0.0,
                'api_donation_amount': 0.0,
                'dik_amount': 0.0,
                'po_amount': 0.0,
                'welfare_amount': 0.0,
                'microfinance_amount': 0.0,
                'expense_amount': 0.0,
                'transfer_in_amount': 0.0,
                'transfer_out_amount': 0.0,
            })
        
        # Update the specific field
        current_value = getattr(shariah_law, field_name, 0.0)
        shariah_law.write({
            field_name: current_value + amount
        })
        
        # Update parent accounts recursively
        if account.parent_id:
            self._update_parent_recursive(shariah_obj, account.parent_id, field_name, amount)

    def _update_parent_recursive(self, shariah_obj, account, field_name, amount):
        """Recursively update parent accounts."""
        if not account:
            return
        
        shariah_law = shariah_obj.search([
            ('analytic_account_id', '=', account.id)
        ], limit=1)
        
        if shariah_law:
            current_value = getattr(shariah_law, field_name, 0.0)
            shariah_law.write({
                field_name: current_value + amount
            })
        
        # Continue to parent
        if account.parent_id:
            self._update_parent_recursive(shariah_obj, account.parent_id, field_name, amount)

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

    def action_member_post(self):
        """Member approval for transfer."""
        for rec in self:
            rec.member_posted = True

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