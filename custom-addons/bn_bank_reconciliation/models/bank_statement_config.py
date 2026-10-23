from odoo import models, fields


class BankStatementConfig(models.Model):
    _name = 'bank.statement.config'
    _description = "Bank Statement Config"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)

    bank_statement_header_line_ids = fields.One2many('bank.statement.config.header', 'bank_statement_config_id', string="Bank Statement Header Lines")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Bank Name must be unique!')
    ]
    