from odoo import api, fields, models


class SadqaJariya(models.Model):
    _inherit = 'sadqa.jariya'

    # The Branches of the application's lines: the record rules match the
    # application on them (security/analytic_scope_rule.xml).
    line_branch_ids = fields.Many2many(
        'account.analytic.account', 'sadqa_jariya_line_branch_rel', 'application_id', 'analytic_account_id',
        string="Line Branches", compute='_compute_line_branch_ids', store=True,
        help="Branches of the disbursement items and recurring lines.")

    @api.depends('line_ids.analytic_account_id', 'recurring_line_ids.analytic_account_id')
    def _compute_line_branch_ids(self):
        for rec in self:
            rec.line_branch_ids = rec.line_ids.analytic_account_id | rec.recurring_line_ids.analytic_account_id
