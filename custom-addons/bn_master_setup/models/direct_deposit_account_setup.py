from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class DirectDepositAccountSetup(models.Model):
    _name = 'direct.deposit.account.setup'
    _description = 'Direct Deposit Account Setup'

    name=fields.Char(string="Name", default="Account Prefix", readonly=True)
