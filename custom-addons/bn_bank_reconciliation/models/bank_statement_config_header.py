from odoo import models, fields


class BankStatementConfigHeader(models.Model):
    _name = 'bank.statement.config.header'
    _description = "Bank Statement Config Header"


    bank_statement_config_id = fields.Many2one('bank.statement.config', string="Bank Statement Config")
    
    header_type_id = fields.Many2one('bank.statement.header.type', string="Header Type")

    name = fields.Char('Header')
    position = fields.Integer('Position', default=-1)
