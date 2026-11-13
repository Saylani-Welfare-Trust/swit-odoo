from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._program_type_specs()
        specs.update({
            'sadqa_jariya': {
                'name': _('Sadqa e Jariya Delivery'), 'code': 'outgoing', 'sequence_code': 'SDJ',
                'src': 'stock', 'dest': 'customer',
            },
        })
        return specs
