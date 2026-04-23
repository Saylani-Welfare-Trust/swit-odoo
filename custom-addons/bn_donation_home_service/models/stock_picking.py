from odoo import models, fields, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    dhs_id = fields.Many2one('donation.home.service', 'Donation Home Service')