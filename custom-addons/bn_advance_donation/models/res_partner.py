from odoo import api, models, fields

from .res_partner_category import DONOR_ACCOUNT_CODE


class ResPartner(models.Model):
    _inherit = "res.partner"


    advance_donation_ids = fields.One2many(
        "advance.donation", "donor_id", string="Advance Donation Disbursements"
    )

    # "Registered In" is the programmes a donee applied to (Welfare,
    # Microfinance ...): Donor Account stays a plain tag of the donor.
    def _donee_programs(self):
        self.ensure_one()
        return self.category_id.filtered(
            lambda tag: tag.registration_program_code and tag.registration_program_code != DONOR_ACCOUNT_CODE)

    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_ids(self):
        for rec in self:
            rec.registered_program_ids = rec._donee_programs()

    @api.depends('category_id', 'category_id.registration_program_code')
    def _compute_registered_program_count(self):
        for rec in self:
            rec.registered_program_count = len(rec._donee_programs())