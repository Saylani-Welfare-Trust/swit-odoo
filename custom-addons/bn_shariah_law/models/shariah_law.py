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
    # -----------------------------------------------------------------
    # MAIN SYNC METHOD
    # -----------------------------------------------------------------

    @api.model
    def _sync_shariah_data(self):

        shariah_record = defaultdict(lambda: {
            'donation': 0.0,
            'purchase': 0.0,
            'expense': 0.0
        })

        daily_changes = defaultdict(lambda: {
            'donation': 0.0,
            'purchase': 0.0,
            'expense': 0.0
        })

        # ============================================================
        # Helper
        # ============================================================

        def add_amounts(analytic_id, donation=0.0, purchase=0.0, expense=0.0):
            if not analytic_id:
                return

            shariah_record[analytic_id]['donation'] += donation
            shariah_record[analytic_id]['purchase'] += purchase
            shariah_record[analytic_id]['expense'] += expense

            daily_changes[analytic_id]['donation'] += donation
            daily_changes[analytic_id]['purchase'] += purchase
            daily_changes[analytic_id]['expense'] += expense

        # ============================================================
        # 1. POS ORDERS
        # ============================================================

        pos_orders = self.env['pos.order'].search([
            ('is_sync_shariah_law', '=', True),
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
                    donation=line.price_subtotal_incl
                )

            order.is_sync_shariah_law = True

        # ============================================================
        # 2. DONATIONS
        # ============================================================

        # donations = self.env['donation'].search([
        #     ('is_sync_shariah_law', '=', False),
        #     ('state', '=', 'posted')
        # ])

        # for donation in donations:

        #     if not donation.product_id:
        #         continue

        #     analytic = self.env['account.analytic.account'].search([
        #         ('product_ids', 'in', [donation.product_id.id])
        #     ], limit=1)

        #     add_amounts(
        #         analytic.id,
        #         donation=donation.amount
        #     )

        #     donation.is_sync_shariah_law = True

        # ============================================================
        # 3. API DONATIONS
        # ============================================================

        # api_donations = self.env['api.donation'].search([
        #     ('is_sync_shariah_law', '=', False)
        # ])

        # for api_don in api_donations:

        #     for line in api_don.donation_item_ids:

        #         product_name = f"{line.donation_type or ''}{line.item or ''}{line.type or ''}"

        #         if not product_name:
        #             continue

        #         found = self.env['gateway.config.line'].search([
        #             ('name', '=', product_name)
        #         ], limit=1)

        #         if not found or not found.product_id:
        #             continue

        #         analytic = self.env['account.analytic.account'].search([
        #             ('product_ids', 'in', [found.product_id.id])
        #         ], limit=1)

        #         add_amounts(
        #             analytic.id,
        #             donation=line.total
        #         )

        #     api_don.is_sync_shariah_law = True

        # ============================================================
        # 4. EXPENSES
        # ============================================================

        # expenses = self.env['hr.expense'].search([
        #     ('is_sync_shariah_law', '=', False),
        #     ('state', '=', 'done')
        # ])

        # for expense in expenses:

        #     if not expense.product_id:
        #         continue

        #     analytic = self.env['account.analytic.account'].search([
        #         ('product_ids', 'in', [expense.product_id.id])
        #     ], limit=1)

        #     add_amounts(
        #         analytic.id,
        #         expense=expense.total_amount_currency
        #     )

        #     expense.is_sync_shariah_law = True

        # ============================================================
        # 5. PURCHASE ORDERS
        # ============================================================

        # purchases = self.env['purchase.order'].search([
        #     ('is_sync_shariah_law', '=', False),
        #     ('state', '=', 'purchase')
        # ])

        # for purchase in purchases:

        #     for line in purchase.order_line:

        #         if not line.product_id:
        #             continue

        #         analytic = self.env['account.analytic.account'].search([
        #             ('product_ids', 'in', [line.product_id.id])
        #         ], limit=1)

        #         add_amounts(
        #             analytic.id,
        #             purchase=line.price_subtotal
        #         )

        #     purchase.is_sync_shariah_law = True

        # ============================================================
        # 6. UPDATE CUMULATIVE (shariah.law)
        # ============================================================

        def update_parent(account, values):
            if not account:
                return

            record = self.env['shariah.law'].search([
                ('analytic_account_id', '=', account.id)
            ], limit=1)

            if record:
                record.write({
                    'donation_amount': record.donation_amount + values['donation'],
                    'purchase_amount': record.purchase_amount + values['purchase'],
                    'expense_amount': record.expense_amount + values['expense'],
                })
            else:
                self.env['shariah.law'].create({
                    'parent_id': account.parent_id.id if account.parent_id else False,
                    'analytic_account_id': account.id,
                    'donation_amount': values['donation'],
                    'purchase_amount': values['purchase'],
                    'expense_amount': values['expense'],
                })

            if account.parent_id:
                update_parent(account.parent_id, values)

        for analytic_id, values in shariah_record.items():

            # raise UserError(f"Debug: Analytic ID: {analytic_id}, Values: {values}")

            account = self.env['account.analytic.account'].browse(analytic_id)

            if account.exists():
                update_parent(account, values)

        # ============================================================
        # 7. UPDATE DAILY BALANCES
        # ============================================================

        today = fields.Date.context_today(self)

        for analytic_id, values in daily_changes.items():

            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', analytic_id),
                ('date', '=', today)
            ], limit=1)

            if daily:
                daily.write({
                    'donation_amount': daily.donation_amount + values['donation'],
                    'purchase': daily.purchase + values['purchase'],
                    'expense': daily.expense + values['expense'],
                })
            else:
                self.env['shariah.daily.balance'].create({
                    'analytic_account_id': analytic_id,
                    'date': today,
                    'donation_amount': values['donation'],
                    'purchase': values['purchase'],
                    'expense': values['expense'],
                })

        # ============================================================
        # 8. FINAL RECALC (if method exists)
        # ============================================================

        all_today = self.env['shariah.daily.balance'].search([
            ('date', '=', today)
        ])

        if hasattr(all_today, "_compute_balances"):
            all_today._compute_balances()

        return True