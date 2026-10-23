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
    reserved_amount = fields.Float(
        'Reserved Amount',
        default=0.0,
        help='The amount reserved for this donation line'
    )   
