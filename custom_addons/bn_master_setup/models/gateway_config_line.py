from odoo import models, fields


class GatewayConfigLine(models.Model):
    _name = 'gateway.config.line'
    _description = "Gateway Config Line"


    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")

    product_id = fields.Many2one('product.product', string="Product")
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    account_id = fields.Many2one('account.account', string="Credit Account")
    
    name = fields.Char('Product Name')