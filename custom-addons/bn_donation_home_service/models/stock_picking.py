from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    dhs_id = fields.Many2one('donation.home.service', 'Donation Home Service')
    
