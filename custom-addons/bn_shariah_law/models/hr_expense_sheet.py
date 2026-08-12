from odoo import models


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    
    def action_approve_expense_sheets(self):
        """
        Approve expense sheets with Shariah Law Blocker check.
        """
        # Get blocker configuration
        blocker = self.env['shariah.law.blocker'].get_blocker_config()

        if blocker and blocker.enable_expense:
            if self.expense_line_ids:
                for line in self.expense_line_ids:
                    analytic_account = self.env['account.analytic.account'].search([('product_ids', 'in', [line.product_id.id])], limit=1)

                    if analytic_account:
                        shariah_closing_balance = self.env['shariah.law'].get_closing_balance(analytic_account.id)
                        
                        if self.total_amount > shariah_closing_balance:
                            raise models.ValidationError(
                                f"Expense amount {self.total_amount} exceeds the closing balance {shariah_closing_balance} for segment '{analytic_account.name}'."
                            )
        
        return super(HrExpenseSheet, self).action_approve_expense_sheets()
        
        