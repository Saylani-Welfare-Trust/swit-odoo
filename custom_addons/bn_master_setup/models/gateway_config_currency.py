from odoo import models, fields


class GatewayConfigCurrency(models.Model):
    _name = 'gateway.config.currency'
    _description = 'Gateway Config Currency'


    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")

    currency_id = fields.Many2one('res.currency', string="Currency")
    account_id = fields.Many2one('account.account', string="Debit Account")