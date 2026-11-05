from odoo import models, fields

class DonationHomeService(models.Model):
    _inherit = 'donation.home.service'


    direct_deposit_id = fields.Many2one('direct.deposit', string="Direct Deposit")