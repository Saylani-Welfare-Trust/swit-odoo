from odoo import api, fields, models


class Welfare(models.Model):
    _inherit = 'welfare'

    # The Branches of the application's lines: the record rules match the
    # application on them (security/analytic_scope_rule.xml).
    line_branch_ids = fields.Many2many(
        'account.analytic.account', 'welfare_line_branch_rel', 'welfare_id', 'analytic_account_id',
        string="Line Branches", compute='_compute_line_branch_ids', store=True,
        help="Branches of the welfare lines and recurring lines.")

    @api.depends('welfare_line_ids.analytic_account_id', 'welfare_recurring_line_ids.analytic_account_id')
    def _compute_line_branch_ids(self):
        for rec in self:
            rec.line_branch_ids = (rec.welfare_line_ids.analytic_account_id
                                   | rec.welfare_recurring_line_ids.analytic_account_id)
