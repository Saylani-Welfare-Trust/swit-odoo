from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    livestock_slaughter_id = fields.Many2one('livestock.slaugther', string='Livestock Slaughter', copy=False, index=True)