from odoo import fields, models


class ConfigBankLine(models.Model):
    _inherit = 'config.bank.header'


    header_type_id = fields.Many2one('header.type', string="Header Type ID")