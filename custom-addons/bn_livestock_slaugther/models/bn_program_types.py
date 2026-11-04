from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'livestock': {
                'name': _('Livestock Slaughter'), 'code': 'internal', 'sequence_code': 'LVS',
                'src': 'stock', 'dest': None,
            },
            'livestock_distribution': {
                'name': _('Livestock Distribution'), 'code': 'outgoing', 'sequence_code': 'LVD',
                'src': 'stock', 'dest': 'customer',
            },
        })
        return specs
