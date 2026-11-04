from odoo import models


class POSCheque(models.Model):
    _inherit = 'pos.cheque'

    def action_clear(self):
        """Cheque/direct deposit payments are held out of livestock until
        cleared - now that this one is, let its POS order's livestock lines
        (if any) fall into livestock."""
        res = super().action_clear()
        pos_orders = self.env['pos.order'].search([('pos_cheque_id', 'in', self.ids)])
        pos_orders._create_livestock_slaughter_records()
        return res
