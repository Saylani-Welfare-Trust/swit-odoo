from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date
from collections import defaultdict

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

    # -----------------------------------------------------------------
    # MAIN SYNC METHOD
    # -----------------------------------------------------------------

    @api.model
    def _sync_shariah_data(self):

        shariah_record = defaultdict(lambda: {
            'pos_donation': 0.0,
            'api_donation': 0.0,
            'dik': 0.0,
            'po': 0.0,
            'welfare': 0.0,
            'microfinance': 0.0,
            'expense': 0.0,
            'transfer_in': 0.0,
            'transfer_out': 0.0
        })

        daily_changes = defaultdict(lambda: {
            'pos_donation': 0.0,
            'api_donation': 0.0,
            'dik': 0.0,
            'po': 0.0,
            'welfare': 0.0,
            'microfinance': 0.0,
            'expense': 0.0,
            'transfer_in': 0.0,
            'transfer_out': 0.0
        })

        # ============================================================
        # Helper
        # ============================================================

        def add_amounts(analytic_id, pos_donation=0.0, api_donation=0.0, dik=0.0, 
                       po=0.0, welfare=0.0, microfinance=0.0, expense=0.0,
                       transfer_in=0.0, transfer_out=0.0):
            if not analytic_id:
                return

            shariah_record[analytic_id]['pos_donation'] += pos_donation
            shariah_record[analytic_id]['api_donation'] += api_donation
            shariah_record[analytic_id]['dik'] += dik
            shariah_record[analytic_id]['po'] += po
            shariah_record[analytic_id]['welfare'] += welfare
            shariah_record[analytic_id]['microfinance'] += microfinance
            shariah_record[analytic_id]['expense'] += expense
            shariah_record[analytic_id]['transfer_in'] += transfer_in
            shariah_record[analytic_id]['transfer_out'] += transfer_out

            daily_changes[analytic_id]['pos_donation'] += pos_donation
            daily_changes[analytic_id]['api_donation'] += api_donation
            daily_changes[analytic_id]['dik'] += dik
            daily_changes[analytic_id]['po'] += po
            daily_changes[analytic_id]['welfare'] += welfare
            daily_changes[analytic_id]['microfinance'] += microfinance
            daily_changes[analytic_id]['expense'] += expense
            daily_changes[analytic_id]['transfer_in'] += transfer_in
            daily_changes[analytic_id]['transfer_out'] += transfer_out

        # ============================================================
        # 1. POS ORDERS (POS Donation)
        # ============================================================

        pos_orders = self.env['pos.order'].search([
            ('is_sync_shariah_law', '=', False),
            ('state', '=', 'done')
        ])

        for order in pos_orders:
            for line in order.lines:
                if not line.product_id:
                    continue

                analytic = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [line.product_id.id])
                ], limit=1)

                add_amounts(
                    analytic.id,
                    pos_donation=line.price_subtotal_incl
                )

            order.is_sync_shariah_law = True

        # ============================================================
        # 2. DONATIONS (DIK)
        # ============================================================

        donations = self.env['donation'].search([
            ('is_sync_shariah_law', '=', False),
            ('state', '=', 'posted')
        ])

        for donation in donations:
            if not donation.product_id:
                continue

            analytic = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [donation.product_id.id])
            ], limit=1)

            add_amounts(
                analytic.id,
                dik=donation.amount
            )

            donation.is_sync_shariah_law = True

        # ============================================================
        # 3. API DONATIONS (API / Wallet)
        # ============================================================

        api_donations = self.env['api.donation'].search([
            ('is_sync_shariah_law', '=', False)
        ])

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

                analytic = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [found.product_id.id])
                ], limit=1)

                add_amounts(
                    analytic.id,
                    api_donation=line.total
                )

            api_don.is_sync_shariah_law = True

        # ============================================================
        # 4. EXPENSES
        # ============================================================

        expenses = self.env['hr.expense'].search([
            ('is_sync_shariah_law', '=', False),
            ('state', '=', 'done')
        ])

        for expense in expenses:
            if not expense.product_id:
                continue

            analytic = self.env['account.analytic.account'].search([
                ('product_ids', 'in', [expense.product_id.id])
            ], limit=1)

            add_amounts(
                analytic.id,
                expense=expense.total_amount_currency
            )

            expense.is_sync_shariah_law = True

        # ============================================================
        # 5. PURCHASE ORDERS (PO)
        # ============================================================

        purchases = self.env['purchase.order'].search([
            ('is_sync_shariah_law', '=', False),
            ('state', '=', 'purchase')
        ])

        for purchase in purchases:
            for line in purchase.order_line:
                if not line.product_id:
                    continue

                analytic = self.env['account.analytic.account'].search([
                    ('product_ids', 'in', [line.product_id.id])
                ], limit=1)

                add_amounts(
                    analytic.id,
                    po=line.price_subtotal
                )

            purchase.is_sync_shariah_law = True

        # ============================================================
        # 6. WELFARE (Cash) - If you have a welfare model
        # ============================================================

        # TODO: Add welfare model sync when available
        # welfare_records = self.env['welfare.model'].search([
        #     ('is_sync_shariah_law', '=', False),
        #     ('state', '=', 'posted')
        # ])
        # for welfare in welfare_records:
        #     if not welfare.product_id:
        #         continue
        #     analytic = self.env['account.analytic.account'].search([
        #         ('product_ids', 'in', [welfare.product_id.id])
        #     ], limit=1)
        #     add_amounts(
        #         analytic.id,
        #         welfare=welfare.amount
        #     )
        #     welfare.is_sync_shariah_law = True

        # ============================================================
        # 7. MICROFINANCE (Cash) - If you have a microfinance model
        # ============================================================

        # TODO: Add microfinance model sync when available
        # microfinance_records = self.env['microfinance.model'].search([
        #     ('is_sync_shariah_law', '=', False),
        #     ('state', '=', 'posted')
        # ])
        # for microfinance in microfinance_records:
        #     if not microfinance.product_id:
        #         continue
        #     analytic = self.env['account.analytic.account'].search([
        #         ('product_ids', 'in', [microfinance.product_id.id])
        #     ], limit=1)
        #     add_amounts(
        #         analytic.id,
        #         microfinance=microfinance.amount
        #     )
        #     microfinance.is_sync_shariah_law = True

        # ============================================================
        # 8. TRANSFERS - From Transfer Model
        # ============================================================

        transfers = self.env['shariah.transfer'].search([
            ('is_sync_shariah_law', '=', False),
            ('state', '=', 'posted')
        ])

        for transfer in transfers:
            # Source account (transfer out)
            if transfer.source_analytic_account_id:
                add_amounts(
                    transfer.source_analytic_account_id.id,
                    transfer_out=transfer.amount
                )
            
            # Destination account (transfer in)
            if transfer.destination_analytic_account_id:
                add_amounts(
                    transfer.destination_analytic_account_id.id,
                    transfer_in=transfer.amount
                )
            
            transfer.is_sync_shariah_law = True

        # ============================================================
        # 9. UPDATE CUMULATIVE (shariah.law)
        # ============================================================

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
            if account.exists():
                update_parent(account, values)

        # ============================================================
        # 10. UPDATE DAILY BALANCES
        # ============================================================

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

        # ============================================================
        # 11. FORCE RECALCULATION OF BALANCES
        # ============================================================

        # Force recompute all daily balances for today
        all_today = self.env['shariah.daily.balance'].search([
            ('date', '=', today)
        ])
        
        if all_today:
            # Trigger recomputation
            all_today._compute_balances()
            all_today._compute_total_donation()

        return True