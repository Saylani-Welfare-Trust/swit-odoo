from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_donee = fields.Boolean(
        string="Is Donee",
        help="Check if this partner is a donee (eligible for recurring contracts)."
    )
    is_recurring = fields.Boolean(
        string="Is Recurring",
        help="Only applicable if this partner is a donee."
    )
