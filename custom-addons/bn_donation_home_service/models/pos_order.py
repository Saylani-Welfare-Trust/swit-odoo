from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _pos_documents(self, extra_data):
        res = super()._pos_documents(extra_data)
        dhs_id = (extra_data.get('dhs') or {}).get('dhs_id')
        return res + [self.env['donation.home.service'].browse(dhs_id).exists() if dhs_id else self.env['donation.home.service']]
