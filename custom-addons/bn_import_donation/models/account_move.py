from odoo import fields, models, exceptions, api


class AccountMove(models.Model):
    _inherit = 'account.move'


    donation_id = fields.Many2one('donation', string="Donation ID")
    fee_box_id = fields.Many2one('fee.box', string="Fee Box ID")