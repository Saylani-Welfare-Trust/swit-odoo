from odoo import models, fields


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    member_approval = fields.Boolean(string='Member Approval', default=False, help="If checked, this account requires member approval for transfers.")
    