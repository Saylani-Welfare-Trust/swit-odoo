from odoo import fields, models, api, _, exceptions


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_ids = fields.One2many('donation', 'partner_id', string='Donation IDs')
    fee_voucher_ids = fields.One2many('fee.box', 'partner_id', string='Fee Voucher IDs')