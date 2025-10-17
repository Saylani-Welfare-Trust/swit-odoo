from odoo import models, fields


class GatewayConfigHeader(models.Model):
    _name = 'gateway.config.header'
    _description = "Gateway Config Header"


    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")
    
    header_type_id = fields.Many2one('header.type', string="Header Type")

    name = fields.Char('Header')
    position = fields.Integer('Position', default=-1)
