from odoo import fields, models


class ConfigBankLine(models.Model):
    _name = 'config.bank.header'
    _description = "Config Bank Header"


    name = fields.Char('Header')

    position = fields.Integer('Position', default=-1)

    config_bank_id = fields.Many2one('config.bank', string="Config Bank ID")