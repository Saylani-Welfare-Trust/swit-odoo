from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DonationHomeService(models.Model):
    _inherit = 'donation.home.service'


    direct_deposit_id = fields.Many2one('direct.deposit', string="Direct Deposit")