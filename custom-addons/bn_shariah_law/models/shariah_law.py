from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law Aggregated Totals"
    _rec_name = 'analytic_account_id'
    _order = 'date desc, analytic_account_id'

    parent_id = fields.Many2one('account.analytic.account', string="Parent Analytic Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    
    # Date tracking
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, index=True)
    
    # Transaction amounts by source (cumulative totals for the day)
    # POSITIVE transactions (increase balance)
    pos_donation_amount = fields.Monetary('POS Donation', currency_field='currency_id', default=0)
    api_donation_amount = fields.Monetary('API / Wallet', currency_field='currency_id', default=0)
    dik_amount = fields.Monetary('DIK', currency_field='currency_id', default=0)
    
    # NEGATIVE transactions (decrease balance)
    po_amount = fields.Monetary('PO', currency_field='currency_id', default=0)
    welfare_amount = fields.Monetary('Welfare (Cash)', currency_field='currency_id', default=0)
    microfinance_amount = fields.Monetary('Microfinance (Cash)', currency_field='currency_id', default=0)
    expense_amount = fields.Monetary('Expense', currency_field='currency_id', default=0)
    
    # Transfer amounts (cumulative totals) - positive for in, negative for out
    transfer_amount = fields.Monetary('Transfer', currency_field='currency_id', default=0)
    
    # Balance fields
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        compute='_compute_opening_balance',
        store=True
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        compute='_compute_closing_balance',
        store=True
    )
    total_donation = fields.Monetary(
        string='Total Donation',
        currency_field='currency_id',
        compute='_compute_total_donation',
        store=True
    )

    @api.depends('pos_donation_amount', 'api_donation_amount', 'dik_amount')
    def _compute_total_donation(self):
        """Compute total donation from all positive sources."""
        for rec in self:
            rec.total_donation = (
                rec.pos_donation_amount + 
                rec.api_donation_amount + 
                rec.dik_amount
            )

    @api.depends('date', 'analytic_account_id')
    def _compute_opening_balance(self):
        """Fetch opening balance from previous day's closing balance."""
        for rec in self:
            # Get previous day's record
            prev_date = rec.date - timedelta(days=1)
            prev_record = self.search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '=', prev_date)
            ], limit=1)
            
            rec.opening_balance = prev_record.closing_balance if prev_record else 0.0

    @api.depends(
        'opening_balance', 'pos_donation_amount', 'api_donation_amount', 
        'dik_amount', 'po_amount', 'welfare_amount', 'microfinance_amount',
        'expense_amount', 'transfer_amount'
    )
    def _compute_closing_balance(self):
        """
        Compute closing balance.
        Closing = Opening + Total Donation + Transfer + PO + Welfare + Microfinance + Expense
        Note: PO, Welfare, Microfinance, and Expense are already negative
        """
        for rec in self:
            rec.closing_balance = (
                rec.opening_balance +
                rec.pos_donation_amount +
                rec.api_donation_amount +
                rec.dik_amount +
                rec.transfer_amount +
                rec.po_amount +
                rec.welfare_amount +
                rec.microfinance_amount +
                rec.expense_amount
            )

    def action_transfer(self):
        return {
            'name': _('Transfer From'),
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    # ============================================================
    # DAILY RESET SCHEDULED ACTION
    # ============================================================

    @api.model
    def _reset_daily_balances(self):
        """
        Scheduled action to reset daily balances.
        This should be run at midnight (or beginning of each day).
        It creates new records for today with opening balance from yesterday's closing.
        """
        _logger.info("Starting daily reset of Shariah Law balances")
        
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)
        
        # Get all active analytic accounts that have shariah.law records
        existing_records = self.search([])
        
        accounts_processed = set()
        records_created = 0
        
        for record in existing_records:
            account = record.analytic_account_id
            if not account or account.id in accounts_processed:
                continue
            
            accounts_processed.add(account.id)
            
            # Check if today's record already exists for this account
            today_record = self.search([
                ('analytic_account_id', '=', account.id),
                ('date', '=', today)
            ], limit=1)
            
            if today_record:
                # If today's record exists, reset its transaction amounts to zero
                # but keep the opening balance (which should already be set)
                today_record.write({
                    'pos_donation_amount': 0.0,
                    'api_donation_amount': 0.0,
                    'dik_amount': 0.0,
                    'po_amount': 0.0,
                    'welfare_amount': 0.0,
                    'microfinance_amount': 0.0,
                    'expense_amount': 0.0,
                    'transfer_amount': 0.0,
                })
                records_created += 1
            else:
                # Get yesterday's closing balance
                yesterday_record = self.search([
                    ('analytic_account_id', '=', account.id),
                    ('date', '=', yesterday)
                ], limit=1)
                
                opening_balance = yesterday_record.closing_balance if yesterday_record else 0.0
                
                # Create today's record with opening balance
                self.create({
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
                records_created += 1
        
        # Also create records for any analytic accounts that don't have shariah.law records yet
        all_analytic_accounts = self.env['account.analytic.account'].search([])
        for account in all_analytic_accounts:
            if account.id not in accounts_processed:
                today_record = self.search([
                    ('analytic_account_id', '=', account.id),
                    ('date', '=', today)
                ], limit=1)
                
                if not today_record:
                    # Get yesterday's closing balance from daily balance model
                    daily_balance = self.env['shariah.daily.balance'].search([
                        ('analytic_account_id', '=', account.id),
                        ('date', '=', yesterday)
                    ], limit=1)
                    
                    opening_balance = daily_balance.closing_balance if daily_balance else 0.0
                    
                    self.create({
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
                    records_created += 1
        
        _logger.info(f"Daily reset completed. Processed {len(accounts_processed)} accounts, created/updated {records_created} records.")
        
        return {
            'processed_accounts': len(accounts_processed),
            'records_created': records_created,
        }

    @api.model
    def _reset_daily_balances_cron(self):
        """
        Cron job wrapper for daily reset.
        This method is called by the scheduled action.
        """
        try:
            result = self._reset_daily_balances()
            _logger.info(f"Daily reset cron completed successfully: {result}")
        except Exception as e:
            _logger.error(f"Error in daily reset cron: {str(e)}")
            raise

    # ============================================================
    # CHECK IF SYNC IS ENABLED FOR A MODULE
    # ============================================================

    def _is_sync_enabled(self, method_name):
        """Check if a specific sync method is enabled in configuration."""
        config = self.env['shariah.law.config'].get_config()
        
        # Config field mapping
        config_field_mapping = {
            '_sync_pos_orders': 'enable_pos_sync',
            '_sync_donations': 'enable_donations_sync',
            '_sync_donation_in_kind': 'enable_dik_sync',
            '_sync_api_donations': 'enable_api_donation_sync',
            '_sync_expenses': 'enable_expense_sync',
            '_sync_purchase_orders': 'enable_purchase_sync',
            '_sync_welfare': 'enable_welfare_sync',
            '_sync_microfinance': 'enable_microfinance_sync',
            '_sync_transfers': 'enable_transfer_sync',
        }
        
        config_field = config_field_mapping.get(method_name)
        if config_field:
            return getattr(config, config_field, False)
        return False

    def _create_sync_log(self, config, module_name, status, message, records_synced=0, error_details='', duration=0):
        """Create a sync log entry."""
        if 'shariah.law.sync.log' in self.env:
            log_vals = {
                'config_id': config.id,
                'module_name': module_name,
                'status': status,
                'message': message,
                'records_synced': records_synced,
                'error_details': error_details,
                'duration': duration,
                'company_id': self.env.company.id,
            }
            self.env['shariah.law.sync.log'].create(log_vals)

    # ============================================================
    # INDIVIDUAL SYNC METHODS WITH CORRECT SIGNS
    # ============================================================

    @api.model
    def _sync_pos_orders(self):
        """Sync POS Orders - POS Donation (POSITIVE)."""
        if not self._is_sync_enabled('_sync_pos_orders'):
            _logger.info("POS Orders sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            pos_orders = self.env['pos.order'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'done')
            ])

            if not pos_orders:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for order in pos_orders:
                for line in order.lines:
                    if not line.product_id:
                        continue

                    # Skip excluded products
                    if line.product_id.display_name.lower() == self.env.company.medical_equipment_security_depsoit_product.lower() or line.product_id.display_name.lower() == self.env.company.microfinance_intallement_product.lower():
                        continue

                    # Get analytic accounts from analytical.product.line
                    analytics = self.env['account.analytic.account'].search([
                        ('product_ids', 'in', [line.product_id.id])
                    ])
                    
                    # Process all analytic accounts found
                    for analytic in analytics:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            pos_donation=line.price_subtotal_incl  # POSITIVE
                        )

                order.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='POS Donations',
                status='success',
                message=f"Synced {len(pos_orders)} POS orders",
                records_synced=len(pos_orders),
                duration=duration
            )

            return {'records_synced': len(pos_orders)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='POS Donations',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    @api.model
    def _sync_donations(self):
        """Sync Donations - API Donation (POSITIVE)."""
        if not self._is_sync_enabled('_sync_donations'):
            _logger.info("Donations sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            donations = self.env['donation'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'posted')
            ])

            if not donations:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for donation in donations:
                if not donation.product_id:
                    continue

                # Get analytic accounts from analytical.product.line
                analytics = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [donation.product_id.id])
                ])

                for analytic in analytics:
                    target_analytic = analytic.analytic_account_id if hasattr(analytic, 'analytic_account_id') else analytic
                    if target_analytic:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            target_analytic.id,
                            api_donation=donation.amount  # POSITIVE
                        )

                donation.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Donations',
                status='success',
                message=f"Synced {len(donations)} donations",
                records_synced=len(donations),
                duration=duration
            )

            return {'records_synced': len(donations)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Donations (API)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    @api.model
    def _sync_api_donations(self):
        """Sync API Donations - API / Wallet (POSITIVE)."""
        if not self._is_sync_enabled('_sync_api_donations'):
            _logger.info("API Donations sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            api_donations = self.env['api.donation'].search([
                ('is_sync_shariah_law', '=', False)
            ])

            if not api_donations:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for api_don in api_donations:
                for line in api_don.donation_item_ids:
                    product_name = f"{line.donation_type or ''}{line.item or ''}{line.type or ''}"
                    if not product_name:
                        continue

                    found = self.env['gateway.config.line'].search([
                        ('name', '=', product_name)
                    ], limit=1)

                    if not found or not found.product_id:
                        continue

                    # Get analytic accounts from analytical.product.line
                    analytics = self.env['account.analytic.account'].search([
                        ('product_ids', 'in', [found.product_id.id])
                    ])

                    for analytic in analytics:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            api_donation=line.total  # POSITIVE
                        )

                api_don.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='API / Wallet Donations',
                status='success',
                message=f"Synced {len(api_donations)} API donations",
                records_synced=len(api_donations),
                duration=duration
            )

            return {'records_synced': len(api_donations)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='API / Wallet Donations',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    @api.model
    def _sync_expenses(self):
        """Sync HR Expenses - Expense (NEGATIVE)."""
        if not self._is_sync_enabled('_sync_expenses'):
            _logger.info("Expenses sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            expenses = self.env['hr.expense'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'done')
            ])

            if not expenses:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for expense in expenses:
                if not expense.product_id:
                    continue

                # Get analytic accounts from account.analytic.account
                analytics = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [expense.product_id.id])
                ])

                for analytic in analytics:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic.id,
                        expense=-expense.total_amount_currency  # NEGATIVE
                    )

                expense.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Expenses',
                status='success',
                message=f"Synced {len(expenses)} expenses",
                records_synced=len(expenses),
                duration=duration
            )

            return {'records_synced': len(expenses)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Expenses',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    @api.model
    def _sync_purchase_orders(self):
        """Sync Purchase Orders - PO (NEGATIVE)."""
        if not self._is_sync_enabled('_sync_purchase_orders'):
            _logger.info("Purchase Orders sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            purchases = self.env['purchase.order'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'purchase')
            ])

            if not purchases:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for purchase in purchases:
                for line in purchase.order_line:
                    if not line.product_id:
                        continue

                    # Get analytic accounts from account.analytic.account
                    analytics = self.env['account.analytic.account'].search([
                        ('product_ids', 'in', [line.product_id.id])
                    ])

                    for analytic in analytics:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            po=-line.price_subtotal  # NEGATIVE
                        )

                purchase.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Purchase Orders (PO)',
                status='success',
                message=f"Synced {len(purchases)} purchase orders",
                records_synced=len(purchases),
                duration=duration
            )

            return {'records_synced': len(purchases)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Purchase Orders (PO)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    @api.model
    def _sync_welfare(self):
        """Sync Welfare records - Only disbursed state (NEGATIVE)."""
        if not self._is_sync_enabled('_sync_welfare'):
            _logger.info("Welfare sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            welfare_records = self.env['welfare'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'disbursed')
            ])

            if not welfare_records:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for welfare in welfare_records:
                total_amount = self._calculate_welfare_amount(welfare)
                
                if total_amount <= 0:
                    continue

                # Get analytic account from welfare
                analytic_account = self._get_analytic_account_from_welfare(welfare)
                
                if analytic_account:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic_account.id,
                        welfare=-total_amount  # NEGATIVE
                    )

                welfare.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Welfare (Cash)',
                status='success',
                message=f"Synced {len(welfare_records)} welfare records",
                records_synced=len(welfare_records),
                duration=duration
            )

            return {'records_synced': len(welfare_records)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Welfare (Cash)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    def _calculate_welfare_amount(self, welfare_record):
        """Calculate the total amount from welfare lines."""
        amount = 0.0
        
        welfare_lines = welfare_record.welfare_line_ids
        
        if not welfare_lines:
            return amount
        
        for line in welfare_lines:
            if line.state == 'disbursed':
                amount += line.total_amount or line.amount or 0.0
        
        if welfare_record.welfare_recurring_line_ids:
            for line in welfare_record.welfare_recurring_line_ids:
                if line.state in ['disbursed', 'collected']:
                    amount += line.total_amount or line.amount or 0.0
        
        return amount

    def _get_analytic_account_from_welfare(self, welfare_record):
        """Get analytic account from welfare record."""
        for line in welfare_record.welfare_line_ids:
            if line.product_id:
                analytics = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [line.product_id.id])
                ])
                for analytic in analytics:
                    return analytic
        
        return False

    @api.model
    def _sync_microfinance(self):
        """Sync Microfinance records - Only Cash type (NEGATIVE)."""
        if not self._is_sync_enabled('_sync_microfinance'):
            _logger.info("Microfinance sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            microfinance_records = self.env['microfinance'].search([
                ('is_sync_shariah_law', '=', False),
                ('asset_type', '=', 'cash'),
                ('state', '=', 'done')
            ])

            if not microfinance_records:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for microfinance in microfinance_records:
                amount = self._calculate_microfinance_amount(microfinance)
                
                if amount <= 0:
                    continue

                analytic_account = self._get_analytic_account_from_microfinance(microfinance)
                
                if analytic_account:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic_account.id,
                        microfinance=-amount  # NEGATIVE
                    )

                microfinance.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Microfinance (Cash)',
                status='success',
                message=f"Synced {len(microfinance_records)} microfinance records",
                records_synced=len(microfinance_records),
                duration=duration
            )

            return {'records_synced': len(microfinance_records)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Microfinance (Cash)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    def _calculate_microfinance_amount(self, microfinance_record):
        """Calculate the total amount from paid installment lines for a microfinance record."""
        amount = 0.0
        
        paid_lines = self.env['microfinance.line'].search([
            ('microfinance_id', '=', microfinance_record.id),
            ('state', '=', 'paid'),
            ('payment_type', '=', 'installment')
        ])
        
        for line in paid_lines:
            amount += line.paid_amount or line.amount or 0.0
        
        return amount

    def _get_analytic_account_from_microfinance(self, microfinance_record):
        """Get analytic account from microfinance record."""
        if microfinance_record.product_id:
            analytics = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [microfinance_record.product_id.id])
            ])
            for analytic in analytics:
                return analytic
        
        return False

    @api.model
    def _sync_transfers(self):
        """Sync Transfers - Transfer In/Out (Cron job for backup sync)."""
        if not self._is_sync_enabled('_sync_transfers'):
            _logger.info("Transfers sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            transfers = self.env['shariah.transfer'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'posted')
            ])

            if not transfers:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for transfer in transfers:
                # For source account - transfer out (NEGATIVE)
                if transfer.source_analytic_account_id:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        transfer.source_analytic_account_id.id,
                        transfer=-transfer.amount  # NEGATIVE
                    )
                
                # For destination account - transfer in (POSITIVE)
                if transfer.destination_analytic_account_id:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        transfer.destination_analytic_account_id.id,
                        transfer=transfer.amount  # POSITIVE
                    )
                
                transfer.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Transfers (Cron Backup)',
                status='success',
                message=f"Synced {len(transfers)} transfers (backup sync)",
                records_synced=len(transfers),
                duration=duration
            )

            return {'records_synced': len(transfers)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Transfers (Cron Backup)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}
    
    @api.model
    def _sync_donation_in_kind(self):
        """Sync Donation In Kind (DIK) records (POSITIVE)."""
        if not self._is_sync_enabled('_sync_donation_in_kind'):
            _logger.info("Donation In Kind sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            dik_records = self.env['donation.in.kind'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'box_validate')
            ])

            if not dik_records:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for dik in dik_records:
                amount = self._calculate_dik_amount(dik)
                
                if amount <= 0:
                    continue

                analytic_account = dik.analytical_account_id or self._get_analytic_account_from_dik(dik)
                
                if analytic_account:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic_account.id,
                        dik=amount  # POSITIVE
                    )

                dik.is_sync_shariah_law = True

            self._update_cumulative_totals(shariah_record)
            self._update_daily_balances(daily_changes)
            self._recompute_balances()

            duration = (datetime.now() - start_time).total_seconds()
            self._create_sync_log(
                config=config,
                module_name='Donation In Kind (DIK)',
                status='success',
                message=f"Synced {len(dik_records)} DIK records",
                records_synced=len(dik_records),
                duration=duration
            )

            return {'records_synced': len(dik_records)}

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self._create_sync_log(
                config=config,
                module_name='Donation In Kind (DIK)',
                status='error',
                message=f"Sync failed: {error_msg}",
                error_details=error_msg,
                duration=duration
            )
            if config.stop_on_error:
                raise
            return {'records_synced': 0, 'error': error_msg}

    def _calculate_dik_amount(self, dik_record):
        """Calculate the total amount for a DIK record."""
        amount = 0.0
        
        if dik_record.account_move_id:
            amount = abs(dik_record.account_move_id.amount_total)
        elif dik_record.donation_in_kind_line_ids:
            for line in dik_record.donation_in_kind_line_ids:
                if line.avg_price and line.quantity:
                    amount += line.avg_price * line.quantity
        elif dik_record.product_id and dik_record.quantity:
            amount = dik_record.product_id.standard_price * dik_record.quantity
            
        return amount

    def _get_analytic_account_from_dik(self, dik_record):
        """Get analytic account from DIK record."""
        if dik_record.product_id:
            analytics = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [dik_record.product_id.id])
            ])
            for analytic in analytics:
                return analytic
        
        return False

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _get_default_record(self):
        """Return default record structure."""
        return {
            'pos_donation': 0.0,      # POSITIVE
            'api_donation': 0.0,      # POSITIVE
            'dik': 0.0,               # POSITIVE
            'po': 0.0,                # NEGATIVE
            'welfare': 0.0,           # NEGATIVE
            'microfinance': 0.0,      # NEGATIVE
            'expense': 0.0,           # NEGATIVE
            'transfer': 0.0           # POSITIVE for IN, NEGATIVE for OUT
        }

    def _add_amounts(self, shariah_record, daily_changes, analytic_id, **kwargs):
        """Helper to add amounts to both shariah_record and daily_changes."""
        if not analytic_id:
            return

        for key, value in kwargs.items():
            if value:
                shariah_record[analytic_id][key] += value
                daily_changes[analytic_id][key] += value

    def _get_analytic_account_from_product(self, product_id):
        """Get analytic account from product."""
        analytics = self.env['account.analytic.account'].search([
            ('product_ids', 'in', [product_id])
        ])
        return analytics[:1] if analytics else False

    def _update_cumulative_totals_with_hierarchy(self, shariah_record):
        """
        Update cumulative totals in shariah.law with hierarchy support.
        This implements the old logic's parent hierarchy update.
        """
        today = fields.Date.context_today(self)
        
        for analytic_id, values in shariah_record.items():
            account = self.env['account.analytic.account'].browse(analytic_id)
            if not account:
                continue
            
            # Get today's record or create it with opening balance
            today_record = self._get_or_create_today_record(account, today)
            
            # Update the current account's today record
            self._update_single_record(today_record, values)
            
            # Update all parent accounts (hierarchy)
            parent = account.parent_id
            while parent:
                parent_record = self._get_or_create_today_record(parent, today)
                self._update_single_record(parent_record, values)
                parent = parent.parent_id

    def _get_or_create_today_record(self, account, today):
        """
        Get or create today's shariah.law record for an account.
        """
        record = self.search([
            ('analytic_account_id', '=', account.id),
            ('date', '=', today)
        ], limit=1)
        
        if not record:
            # Get yesterday's closing balance
            yesterday = today - timedelta(days=1)
            yesterday_record = self.search([
                ('analytic_account_id', '=', account.id),
                ('date', '=', yesterday)
            ], limit=1)
            
            opening_balance = yesterday_record.closing_balance if yesterday_record else 0.0
            
            record = self.create({
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
        
        return record

    def _update_single_record(self, record, values):
        """
        Update a single shariah.law record with values.
        """
        if not record:
            return

        update_vals = {}
        
        # Map values to fields
        field_mapping = {
            'pos_donation': 'pos_donation_amount',
            'api_donation': 'api_donation_amount',
            'dik': 'dik_amount',
            'po': 'po_amount',
            'welfare': 'welfare_amount',
            'microfinance': 'microfinance_amount',
            'expense': 'expense_amount',
            'transfer': 'transfer_amount',
        }
        
        for key, value in values.items():
            if value:
                mapped_field = field_mapping.get(key, key)
                current_value = getattr(record, mapped_field, 0.0)
                update_vals[mapped_field] = current_value + value

        if update_vals:
            record.write(update_vals)

    def _update_cumulative_totals(self, shariah_record):
        """Update cumulative totals in shariah.law."""
        self._update_cumulative_totals_with_hierarchy(shariah_record)

    def _update_daily_balances(self, daily_changes):
        """Update daily balances."""
        today = fields.Date.context_today(self)

        for analytic_id, values in daily_changes.items():
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', analytic_id),
                ('date', '=', today)
            ], limit=1)

            if daily:
                daily.write({
                    'pos_donation': daily.pos_donation + values['pos_donation'],
                    'api_donation': daily.api_donation + values['api_donation'],
                    'dik': daily.dik + values['dik'],
                    'po': daily.po + values['po'],
                    'welfare': daily.welfare + values['welfare'],
                    'microfinance': daily.microfinance + values['microfinance'],
                    'expense': daily.expense + values['expense'],
                    'transfer': daily.transfer + values['transfer'],
                })
            else:
                self.env['shariah.daily.balance'].create({
                    'analytic_account_id': analytic_id,
                    'date': today,
                    'pos_donation': values['pos_donation'],
                    'api_donation': values['api_donation'],
                    'dik': values['dik'],
                    'po': values['po'],
                    'welfare': values['welfare'],
                    'microfinance': values['microfinance'],
                    'expense': values['expense'],
                    'transfer': values['transfer'],
                })

    def _recompute_balances(self):
        """Force recomputation of all balances for today."""
        today = fields.Date.context_today(self)
        all_today = self.env['shariah.daily.balance'].search([
            ('date', '=', today)
        ])
        
        if all_today:
            all_today._compute_balances()
            all_today._compute_total_donation()

    _sql_constraints = [
        ('unique_account_date', 'unique(analytic_account_id, date)', 
         'Only one record per account per day is allowed.')
    ]