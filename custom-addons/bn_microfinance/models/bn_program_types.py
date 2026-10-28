from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'microfinance_delivery': {
                'name': _('Microfinance Delivery'), 'code': 'outgoing', 'sequence_code': 'MFD',
                'src': 'stock', 'dest': 'customer',
            },
            'microfinance_recovery': {
                'name': _('Microfinance Recovery'), 'code': 'incoming', 'sequence_code': 'MFR',
                'src': 'customer', 'dest': 'stock',
            },
        })
        return specs
