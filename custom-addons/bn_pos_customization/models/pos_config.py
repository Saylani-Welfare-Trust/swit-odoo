from odoo import models, fields, api


class POSConfig(models.Model):
    _inherit = 'pos.config'

    user_ids = fields.Many2many('res.users', string="Users")
    analytic_account_id = fields.Many2one(
        'account.analytic.account', 
        string="Branch Analytic Account",
        help="Select the branch analytic account to print on the POS receipt."
    )
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        fields_list.append('analytic_account_id')
        return fields_list