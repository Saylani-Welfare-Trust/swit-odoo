from odoo import models, fields


class StockQuant(models.Model):
    _inherit = 'stock.quant'
    

    reason = fields.Text(string="Reason")