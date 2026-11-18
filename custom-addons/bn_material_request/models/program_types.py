from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._program_type_specs()
        specs.update({
            'material_request': {
                'name': _('Material Request'), 'code': 'internal', 'sequence_code': 'MR',
                'src': 'stock', 'dest': None,
            },
        })
        return specs
