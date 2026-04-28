from odoo import models, fields


class GatewayConfigLine(models.Model):
    _name = 'gateway.config.line'
    _description = "Gateway Config Line"


    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")

    product_id = fields.Many2one('product.product', string="Product")
    
    name = fields.Char('Product Name')