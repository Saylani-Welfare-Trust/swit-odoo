from odoo import models,fields,api

class AccountAnalyticApplicability(models.Model):
    _inherit = 'account.analytic.applicability'
    _description = "Analytic Plan's Applicabilities"

    business_domain = fields.Selection(
        selection_add=[
            ('location', 'Location'),
            ('chart_of_account', 'Chart of Account')
        ],
        ondelete={
            'location': 'cascade',
            'chart_of_account': 'cascade'
        },
    )
    account_id = fields.Many2one('account.account', 'Account')

    # company_id = fields.Many2one('res.company', 'Location')