from odoo import models, _
from odoo.exceptions import UserError


class ResCurrency(models.Model):
    _inherit = 'res.currency'


    def _has_accounting_entries(self):
        """ Returns True iff this currency has been used to generate (hence, round)
        some move lines (either as their foreign currency, or as the main currency).
        """
        return False
    
    def write(self, vals):
        if 'rounding' in vals:
            rounding_val = vals['rounding']
            for record in self:
                if (rounding_val > record.rounding or rounding_val == 0) and record._has_accounting_entries():
                    raise UserError(_(f"{rounding_val > record.rounding or rounding_val == 0}"))

        return super(ResCurrency, self).write(vals)