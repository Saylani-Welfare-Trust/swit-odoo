from odoo import models, fields


class DonationInKind(models.Model):
    _inherit = 'donation.in.kind'


    is_sync_shariah_law = fields.Boolean('Is Synced (Shariah Law)', default=False, tracking=True)