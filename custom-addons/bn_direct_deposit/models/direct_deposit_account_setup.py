from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class DirectDepositAccountSetup(models.Model):
    _name = 'direct.deposit.account.setup'
    _description = 'Direct Deposit Account Setup'


    name = fields.Char(string="Name", default="Account Prefix")

    @api.model
    def _bn_setup_default_prefix(self):
        """Data hook: the default receivable account prefix (formerly loaded by
        bn_master_setup), created only when no prefix is configured yet."""
        if not self.sudo().search_count([]):
            self.sudo().create({'name': '1121001'})
