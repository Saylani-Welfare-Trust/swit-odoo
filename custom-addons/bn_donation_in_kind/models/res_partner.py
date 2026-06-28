from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_in_kind_ids = fields.One2many('donation.in.kind', 'donor_id', string="Donation In Kinds")