from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'


    bank_journal_id = fields.Many2one('account.journal', string='Bank')