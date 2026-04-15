from odoo import models, fields, api


class AdvanceDonationLineSync(models.Model):
    """Extend advance donation line with reservation status"""
    _name = 'advance.donation.lines'
    _inherit = 'advance.donation.lines'

    # Simple boolean to track if this donation line is reserved by a welfare/recurring line
    is_reserved = fields.Boolean(
        'Reserved',
        default=False,
        help='Indicates if this donation line is reserved for a welfare line or recurring order'
    )
