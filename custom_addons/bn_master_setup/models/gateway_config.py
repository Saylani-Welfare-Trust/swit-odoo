from odoo import models, fields


type_selection = [
    ('gateway', 'Gateway'),
    ('api', 'API')
]


class GatewayConfig(models.Model):
    _name = 'gateway.config'
    _description = "Gateway Config"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)

    type = fields.Selection(selection=type_selection, string="Type", tracking=True)

    account_id = fields.Many2one('account.account', string="Debit Account", tracking=True)

    gateway_config_line_ids = fields.One2many('gateway.config.line', 'gateway_config_id', string="Gateway Config Lines")
    gateway_config_header_ids = fields.One2many('gateway.config.header', 'gateway_config_id', string="Gateway Config Headers")
    gateway_config_currency_ids = fields.One2many('gateway.config.currency', 'gateway_config_id', string="Gateway Config Currencies")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Bank Name must be unique!')
    ]
    