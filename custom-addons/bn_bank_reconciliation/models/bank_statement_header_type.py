from odoo import models, fields


class BankStatementHeaderType(models.Model):
    _name = 'bank.statement.header.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Bank Statement Header Type"



    name = fields.Char('Name')