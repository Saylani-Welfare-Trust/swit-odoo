from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DirectDepositAccountSetup(models.Model):
    _name = 'direct.deposit.account.setup'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Direct Deposit Account Setup'


    name = fields.Char(string="Name", default="Account Prefix")

    @api.model_create_multi
    def create(self, vals_list):
        # one setup only: a second record would leave the choice to chance
        if self.sudo().search_count([]) + len(vals_list) > 1:
            raise UserError(_("There is already a Direct Deposit Account Setup: edit it instead of adding another."))
        return super().create(vals_list)

    @api.model
    def _setup_default_prefix(self):
        """Data hook: the default receivable account prefix (formerly loaded by
        bn_master_setup), created only when no prefix is configured yet."""
        if not self.sudo().search_count([]):
            self.sudo().create({'name': '1121001'})
