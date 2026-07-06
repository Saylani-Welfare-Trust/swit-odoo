from odoo import api, fields, models, _
from collections import defaultdict
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law Aggregated Totals"
    _rec_name = 'analytic_account_id'

    parent_id = fields.Many2one('account.analytic.account', string="Parent Analytic Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    # Transaction amounts by source (cumulative totals)
    pos_donation_amount = fields.Monetary('POS Donation', currency_field='currency_id', default=0)
    api_donation_amount = fields.Monetary('API / Wallet', currency_field='currency_id', default=0)
    dik_amount = fields.Monetary('DIK', currency_field='currency_id', default=0)
    po_amount = fields.Monetary('PO', currency_field='currency_id', default=0)
    welfare_amount = fields.Monetary('Welfare (Cash)', currency_field='currency_id', default=0)
    microfinance_amount = fields.Monetary('Microfinance (Cash)', currency_field='currency_id', default=0)
    expense_amount = fields.Monetary('Expense', currency_field='currency_id', default=0)
    
    # Transfer amounts (cumulative totals)
    transfer_in_amount = fields.Monetary('Transfer In', currency_field='currency_id', default=0)
    transfer_out_amount = fields.Monetary('Transfer Out', currency_field='currency_id', default=0)
    
    # Computed fields
    total_donation = fields.Monetary(
        string='Total Donation',
        currency_field='currency_id',
        compute='_compute_total_donation',
        store=True
    )
    net_transfer = fields.Monetary(
        string='Net Transfer',
        currency_field='currency_id',
        compute='_compute_net_transfer',
        store=True
    )
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        compute='_compute_opening_balance',
        store=False
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        compute='_compute_closing_balance',
        store=False
    )

    @api.depends('pos_donation_amount', 'api_donation_amount', 'dik_amount', 
                 'po_amount', 'welfare_amount', 'microfinance_amount')
    def _compute_total_donation(self):
        """Compute total donation from all sources."""
        for rec in self:
            rec.total_donation = (
                rec.pos_donation_amount + 
                rec.api_donation_amount + 
                rec.dik_amount + 
                rec.po_amount + 
                rec.welfare_amount + 
                rec.microfinance_amount
            )

    @api.depends('transfer_in_amount', 'transfer_out_amount')
    def _compute_net_transfer(self):
        """Compute net transfer (in - out)."""
        for rec in self:
            rec.net_transfer = rec.transfer_in_amount - rec.transfer_out_amount

    def _compute_opening_balance(self):
        """Fetch today's opening balance from daily balance model."""
        today = fields.Date.context_today(self)
        for rec in self:
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            rec.opening_balance = daily.opening_balance if daily else 0.0

    def _compute_closing_balance(self):
        """Compute closing balance from daily balance model."""
        today = fields.Date.context_today(self)
        for rec in self:
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            rec.closing_balance = daily.closing_balance if daily else 0.0

    def action_transfer(self):
        return {
            'name': _('Transfer From'),
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

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
    # INDIVIDUAL SYNC METHODS WITH CONFIG CHECK
    # ============================================================

    @api.model
    def _sync_pos_orders(self):
        """Sync POS Orders - POS Donation."""
        # Check if enabled in configuration
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

                    analytic = self._get_analytic_account_from_product(line.product_id.id)
                    if analytic:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            pos_donation=line.price_subtotal_incl
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
        """Sync Donations - DIK."""
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

                analytic = self._get_analytic_account_from_product(donation.product_id.id)
                if analytic:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic.id,
                        api_donation=donation.amount
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
                module_name='Donations (DIK)',
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
        """Sync API Donations - API / Wallet."""
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

                    analytic = self._get_analytic_account_from_product(found.product_id.id)
                    if analytic:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            api_donation=line.total
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
        """Sync HR Expenses - Expense."""
        if not self._is_sync_enabled('_sync_expenses'):
            _logger.info("Expenses sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            expenses = self.env['hr.expense'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'approved')
            ])

            if not expenses:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for expense in expenses:
                if not expense.product_id:
                    continue

                analytic = self._get_analytic_account_from_product(expense.product_id.id)
                if analytic:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic.id,
                        expense=expense.total_amount_currency
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
        """Sync Purchase Orders - PO."""
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

                    analytic = self._get_analytic_account_from_product(line.product_id.id)
                    if analytic:
                        self._add_amounts(
                            shariah_record, daily_changes,
                            analytic.id,
                            po=line.price_subtotal
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
        """Sync Welfare records - Only disbursed state."""
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

                analytic_account = self._get_analytic_account_from_welfare(welfare)
                
                if analytic_account:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        analytic_account.id,
                        welfare=total_amount
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
                analytic = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [line.product_id.id])
                ], limit=1)
                if analytic:
                    return analytic
        
        return False

    @api.model
    def _sync_microfinance(self):
        """Sync Microfinance records - Only Cash type."""
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
                        microfinance=amount
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
            analytic = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [microfinance_record.product_id.id])
            ], limit=1)
            if analytic:
                return analytic
        
        return False

    @api.model
    def _sync_transfers(self):
        """Sync Transfers - Transfer In/Out (Cron job for backup sync)."""
        # Check if enabled in configuration
        if not self._is_sync_enabled('_sync_transfers'):
            _logger.info("Transfers sync is disabled in configuration")
            return {'records_synced': 0, 'skipped': True}

        config = self.env['shariah.law.config'].get_config()
        start_time = datetime.now()
        
        try:
            # Get transfers that are posted but not synced
            # This catches any transfers that weren't synced instantly
            transfers = self.env['shariah.transfer'].search([
                ('is_sync_shariah_law', '=', False),
                ('state', '=', 'posted')
            ])

            if not transfers:
                return {'records_synced': 0}

            shariah_record = defaultdict(lambda: self._get_default_record())
            daily_changes = defaultdict(lambda: self._get_default_record())

            for transfer in transfers:
                if transfer.source_analytic_account_id:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        transfer.source_analytic_account_id.id,
                        transfer_out=transfer.amount
                    )
                
                if transfer.destination_analytic_account_id:
                    self._add_amounts(
                        shariah_record, daily_changes,
                        transfer.destination_analytic_account_id.id,
                        transfer_in=transfer.amount
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
        """Sync Donation In Kind (DIK) records."""
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
                        dik=amount
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
            analytic = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [dik_record.product_id.id])
            ], limit=1)
            if analytic:
                return analytic
        
        return False

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _get_default_record(self):
        """Return default record structure."""
        return {
            'pos_donation': 0.0,
            'api_donation': 0.0,
            'dik': 0.0,
            'po': 0.0,
            'welfare': 0.0,
            'microfinance': 0.0,
            'expense': 0.0,
            'transfer_in': 0.0,
            'transfer_out': 0.0
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
        return self.env['account.analytic.account'].search([
            ('product_ids', 'in', [product_id])
        ], limit=1)

    def _update_cumulative_totals(self, shariah_record):
        """Update cumulative totals in shariah.law."""
        def update_parent(account, values):
            if not account:
                return

            record = self.env['shariah.law'].search([
                ('analytic_account_id', '=', account.id)
            ], limit=1)

            if record:
                record.write({
                    'pos_donation_amount': record.pos_donation_amount + values['pos_donation'],
                    'api_donation_amount': record.api_donation_amount + values['api_donation'],
                    'dik_amount': record.dik_amount + values['dik'],
                    'po_amount': record.po_amount + values['po'],
                    'welfare_amount': record.welfare_amount + values['welfare'],
                    'microfinance_amount': record.microfinance_amount + values['microfinance'],
                    'expense_amount': record.expense_amount + values['expense'],
                    'transfer_in_amount': record.transfer_in_amount + values['transfer_in'],
                    'transfer_out_amount': record.transfer_out_amount + values['transfer_out'],
                })
            else:
                self.env['shariah.law'].create({
                    'parent_id': account.parent_id.id if account.parent_id else False,
                    'analytic_account_id': account.id,
                    'pos_donation_amount': values['pos_donation'],
                    'api_donation_amount': values['api_donation'],
                    'dik_amount': values['dik'],
                    'po_amount': values['po'],
                    'welfare_amount': values['welfare'],
                    'microfinance_amount': values['microfinance'],
                    'expense_amount': values['expense'],
                    'transfer_in_amount': values['transfer_in'],
                    'transfer_out_amount': values['transfer_out'],
                })

            if account.parent_id:
                update_parent(account.parent_id, values)

        for analytic_id, values in shariah_record.items():
            account = self.env['account.analytic.account'].browse(analytic_id)
            if account:
                update_parent(account, values)

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
                    'transfer_in': daily.transfer_in + values['transfer_in'],
                    'transfer_out': daily.transfer_out + values['transfer_out'],
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
                    'transfer_in': values['transfer_in'],
                    'transfer_out': values['transfer_out'],
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