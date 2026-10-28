from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'qurbani': {
                'name': _('Qurbani Distribution'), 'code': 'outgoing', 'sequence_code': 'QRB',
                'src': 'stock', 'dest': 'customer',
            },
        })
        return specs
