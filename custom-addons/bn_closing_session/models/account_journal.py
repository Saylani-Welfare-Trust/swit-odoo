from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'


    show_in_pos = fields.Boolean('Show in POS')