# Add this code to your pos.order model extension
from odoo import models
from odoo.exceptions import UserError
class PosOrder(models.Model):
    _inherit = 'pos.order'

    def export_for_printing(self):
        res = super(PosOrder, self).export_for_printing()
        # Fetch cover image
        cover_image = self.env['dn.cover.image'].search([], limit=1)
        raise UserError("No cover image found.") if not cover_image else None
        res['cover_image'] = cover_image.image if cover_image and cover_image.image else False
        return res