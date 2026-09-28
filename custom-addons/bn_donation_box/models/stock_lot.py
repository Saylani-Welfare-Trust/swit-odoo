from odoo import models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'


    lot_consume = fields.Boolean('Lot Consume', default=False)
    is_not_return = fields.Boolean('Is not return', default=False)