from odoo import fields, models


class DonationBoxRegistrationInstallation(models.Model):
    _inherit = 'donation.box.registration.installation'


    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch", tracking=True)

    def write(self, vals):
        result = super().write(vals)

        if vals.get('status') == 'close':
            keys = self.env['key'].search([
                '|',
                ('donation_box_registration_installation_id', 'in', self.ids),
                ('lot_id', 'in', self.mapped('lot_id').ids),
            ])
            keys.write({'state': 'closed'})

        return result