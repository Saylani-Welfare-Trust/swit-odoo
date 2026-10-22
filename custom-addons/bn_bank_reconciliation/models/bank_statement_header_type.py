from odoo import models, fields


class BankStatementHeaderType(models.Model):
    _name = 'bank.statement.header.type'
    _description = "Bank Statement Header Type"


    name = fields.Char('Name')