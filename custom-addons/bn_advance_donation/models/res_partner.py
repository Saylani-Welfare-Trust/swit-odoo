from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"
    

    advance_donation_ids = fields.One2many(
        "advance.donation", "donor_id", string="Advance Donation Disbursements"
    )