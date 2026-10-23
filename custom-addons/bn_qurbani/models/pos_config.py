from odoo import models, fields


class POSConfig(models.Model):
    _inherit = 'pos.config'

    
    city_id = fields.Many2one('stock.location', string="City")
    distribution_id = fields.Many2one('stock.location', string="Distribution")