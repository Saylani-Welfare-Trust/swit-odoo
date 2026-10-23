from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_donation_in_kind = fields.Boolean('Is Donation In Kind', tracking=True)