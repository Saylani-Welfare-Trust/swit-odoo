from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'



    account_default_pos_restricted_receivable_account_id = fields.Many2one(string='Default Account Receivable (PoS)', related='company_id.account_default_pos_restricted_receivable_account_id', readonly=False, check_company=True)
    account_default_pos_unrestricted_receivable_account_id = fields.Many2one(string='Default Account Unreceivable (PoS)', related='company_id.account_default_pos_unrestricted_receivable_account_id', readonly=False, check_company=True)