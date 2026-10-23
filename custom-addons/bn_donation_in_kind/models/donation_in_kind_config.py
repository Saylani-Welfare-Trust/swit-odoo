from odoo import models, fields


class DonationInKindConfig(models.Model):
    _name = 'donation.in.kind.config'
    _description = "Donation In Kind Config"


    location_id = fields.Many2one('stock.location', string='Location')
    picking_type_id = fields.Many2one('stock.picking.type', string='Operations Types')
    journal_id = fields.Many2one('account.journal', string='Journal')