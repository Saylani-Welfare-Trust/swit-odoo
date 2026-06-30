from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date

class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law Aggregated Totals"
    _rec_name = 'analytic_account_id'

    parent_id = fields.Many2one('account.analytic.account', string="Parent Analytic Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    # Cumulative totals
    donation_amount = fields.Monetary('Donation', currency_field='currency_id', default=0)
    purchase_amount = fields.Monetary('Purchase', currency_field='currency_id', default=0)
    expense_amount = fields.Monetary('Expense', currency_field='currency_id', default=0)

    # Opening and Closing balances (computed from daily records)
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        compute='_compute_balances_from_daily',
        store=False
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        compute='_compute_balances_from_daily',
        store=False
    )

    def _compute_balances_from_daily(self):
        """Fetch today's opening and closing from the daily balance model."""
        today = fields.Date.context_today(self)
        for rec in self:
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            if daily:
                rec.opening_balance = daily.opening_balance
                rec.closing_balance = daily.closing_balance
            else:
                rec.opening_balance = 0.0
                rec.closing_balance = 0.0

    def action_transfer(self):
        return {
            'name': _('Transfer From'),
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _sync_shariah_data(self):
        """
        Synchronize all un-synced transactions and update daily balances.
        Called by the cron job daily.
        """

        # Helper to add amounts to both aggregate and daily dictionaries
        def add_amounts(analytic_id, donation=0, purchase=0, expense=0):
            if analytic_id not in shariah_record:
                shariah_record[analytic_id] = {'donation_amount': 0, 'purchase': 0, 'expense': 0}
            shariah_record[analytic_id]['donation_amount'] += donation
            shariah_record[analytic_id]['purchase'] += purchase
            shariah_record[analytic_id]['expense'] += expense

            if analytic_id not in daily_changes:
                daily_changes[analytic_id] = {'donation_amount': 0, 'purchase': 0, 'expense': 0}
            daily_changes[analytic_id]['donation_amount'] += donation
            daily_changes[analytic_id]['purchase'] += purchase
            daily_changes[analytic_id]['expense'] += expense

        shariah_record = {}
        daily_changes = {}

        # 1. POS Orders
        pos_orders = self.env['pos.order'].search([('is_sync_shariah_law', '=', False), ('state', 'in', ['cfo_approval', 'paid'])])
        for order in pos_orders:
            for line in order.lines:
                if not line.product_id or line.product_id.name == self.company_id.medical_equipment_security_depsoit_product:
                    continue
                analytical_lines = self.env['analytical.product.line'].search([('product_ids', 'in', [line.product_id.id])])
                for a_line in analytical_lines:
                    analytic_id = a_line.analytic_account_id.id
                    add_amounts(analytic_id, donation=line.price_subtotal_incl)
            order.is_sync_shariah_law = True

        # 2. Donations (model 'donation')
        donations = self.env['donation'].search([('is_sync_shariah_law', '=', False), ('state', '=', 'posted')])
        for donation in donations:
            if not donation.product_id:
                continue
            analytical_lines = self.env['analytical.product.line'].search([('product_ids', 'in', [donation.product_id.id])])
            for a_line in analytical_lines:
                categ_name = donation.product_id.categ_id.complete_name.lower() if donation.product_id.categ_id else ''
                if not categ_name:
                    continue
                analytic_id = a_line.analytic_account_id.id
                add_amounts(analytic_id, donation=donation.amount)
            donation.is_sync_shariah_law = True

        # 3. API Donations (model 'api.donation')
        api_donations = self.env['api.donation'].search([('is_sync_shariah_law', '=', False)])
        for api_don in api_donations:
            for line in api_don.donation_item_ids:
                product_name = f"{line.donation_type or ''}{line.item or ''}{line.type or ''}"
                if not product_name:
                    continue
                found = self.env['gateway.config.line'].search([('name', '=', product_name)], limit=1)
                if not found or not found.product_id:
                    continue
                analytical_lines = self.env['analytical.product.line'].search([('product_ids', 'in', [found.product_id.id])])
                for a_line in analytical_lines:
                    analytic_id = a_line.analytic_account_id.id
                    add_amounts(analytic_id, donation=line.total)
                    
            api_don.is_sync_shariah_law = True

        # 4. Expenses (hr.expense)
        expenses = self.env['hr.expense'].search([('is_sync_shariah_law', '=', False), ('state', '=', 'done')])
        for expense in expenses:
            if not expense.product_id:
                continue
            analytical_lines = self.env['analytical.product.line'].search([('product_ids', 'in', [expense.product_id.id])])
            for a_line in analytical_lines:
                analytic_id = a_line.analytic_account_id.id
                add_amounts(analytic_id, expense=expense.total_amount_currency)
            expense.is_sync_shariah_law = True

        # 5. Purchase Orders
        purchases = self.env['purchase.order'].search([('is_sync_shariah_law', '=', False), ('state', '=', 'purchase')])
        for purchase in purchases:
            for line in purchase.order_line:
                if not line.product_id:
                    continue
                analytical_lines = self.env['analytical.product.line'].search([('product_ids', 'in', [line.product_id.id])])
                for a_line in analytical_lines:
                    analytic_id = a_line.analytic_account_id.id
                    add_amounts(analytic_id, purchase=line.price_subtotal)
            purchase.is_sync_shariah_law = True

        # 6. Process unposted transfers
        draft_transfers = self.env['shariah.transfer'].search([('state', '=', 'draft')])
        for transfer in draft_transfers:
            transfer.action_post()

        # ------------------------------------------------------------
        # Update aggregate (shariah.law) – cumulative totals
        # ------------------------------------------------------------
        for analytic_id, values in shariah_record.items():
            analytic_account = self.env['account.analytic.account'].browse(analytic_id)
            if not analytic_account.exists():
                continue

            def create_or_update_parent(account, amounts):
                parent = account.parent_id
                sh = self.env['shariah.law'].search([('analytic_account_id', '=', account.id)], limit=1)
                if sh:
                    sh.write({
                        'inflow_restricted_amount': sh.inflow_restricted_amount + amounts.get('inflow_restricted', 0),
                        'inflow_unrestricted_amount': sh.inflow_unrestricted_amount + amounts.get('inflow_unrestricted', 0),
                        'purchase_amount': sh.purchase_amount + amounts.get('purchase', 0),
                        'expense_amount': sh.expense_amount + amounts.get('expense', 0),
                    })
                else:
                    self.env['shariah.law'].create({
                        'parent_id': parent.id if parent else False,
                        'analytic_account_id': account.id,
                        'inflow_restricted_amount': amounts.get('inflow_restricted', 0),
                        'inflow_unrestricted_amount': amounts.get('inflow_unrestricted', 0),
                        'purchase_amount': amounts.get('purchase', 0),
                        'expense_amount': amounts.get('expense', 0),
                    })
                if parent:
                    create_or_update_parent(parent, amounts)

            create_or_update_parent(analytic_account, values)

        # ------------------------------------------------------------
        # Update daily balances (shariah.daily.balance)
        # ------------------------------------------------------------
        today = fields.Date.context_today(self)
        for analytic_id, changes in daily_changes.items():
            analytic_account = self.env['account.analytic.account'].browse(analytic_id)
            if not analytic_account.exists():
                continue
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', analytic_id),
                ('date', '=', today)
            ], limit=1)
            if daily:
                daily.write({
                    'inflow_restricted': daily.inflow_restricted + changes.get('inflow_restricted', 0),
                    'inflow_unrestricted': daily.inflow_unrestricted + changes.get('inflow_unrestricted', 0),
                    'purchase': daily.purchase + changes.get('purchase', 0),
                    'expense': daily.expense + changes.get('expense', 0),
                })
            else:
                self.env['shariah.daily.balance'].create({
                    'analytic_account_id': analytic_id,
                    'date': today,
                    'inflow_restricted': changes.get('inflow_restricted', 0),
                    'inflow_unrestricted': changes.get('inflow_unrestricted', 0),
                    'purchase': changes.get('purchase', 0),
                    'expense': changes.get('expense', 0),
                })

        # Recompute balances for all daily records of today
        all_today = self.env['shariah.daily.balance'].search([('date', '=', today)])
        all_today._compute_balances()

        return True