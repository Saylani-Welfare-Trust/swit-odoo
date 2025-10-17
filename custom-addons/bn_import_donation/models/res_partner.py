from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_ids = fields.One2many('donation', 'donor_id', string="Donations")
    api_donation_ids = fields.One2many('api.donation', 'donor_id', string="API Donations")