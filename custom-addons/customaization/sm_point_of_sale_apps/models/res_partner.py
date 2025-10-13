from odoo import fields, models, api, exceptions


class ResPartner(models.Model):
    _inherit = 'res.partner'


    pos_donation_ids = fields.One2many('pos.order', 'partner_id', string="POS Donation IDs")


    @api.model
    def create_from_ui(self, partner):
        # raise exceptions.ValidationError(str(partner))

        country_id = self.env['res.country'].search([('name', 'ilike', partner.get('phone_code_id'))]).id

        partner['phone_code_id'] = country_id

        return super(ResPartner, self).create_from_ui(partner)