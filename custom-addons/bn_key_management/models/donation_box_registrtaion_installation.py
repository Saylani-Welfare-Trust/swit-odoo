from odoo import fields, models


class DonationBoxRegistrationInstallation(models.Model):
    _inherit = 'donation.box.registration.installation'


    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch", tracking=True)


    def action_approved(self):
        self.key_bunch_id.rider_id = self.rider_id.id

        super(DonationBoxRegistrationInstallation, self).action_approved()