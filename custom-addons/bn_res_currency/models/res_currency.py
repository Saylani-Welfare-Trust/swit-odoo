from odoo import models, fields


class ResCurrency(models.Model):
    _inherit = 'res.currency'


    def _has_accounting_entries(self):
        """ Returns True iff this currency has been used to generate (hence, round)
        some move lines (either as their foreign currency, or as the main currency).
        """
        return False