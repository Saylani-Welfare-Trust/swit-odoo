from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_box_registration_installation_ids = fields.One2many('donation.box.registration.installation', 'donor_id', string="Donation Box Registrations")