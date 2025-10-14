from odoo import models, fields

class PosOrder(models.Model):
    _inherit = 'pos.order'

    x_confirmed_for_next_day = fields.Boolean(
        string="Confirmed for Next Day",
        default=False,
        help="Welfare has confirmed this order for next‑day packing"
    )
