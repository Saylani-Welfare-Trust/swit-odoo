from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'donation_in_kind': {
                'name': _('Donation In Kind'), 'code': 'incoming', 'sequence_code': 'DIK',
                'src': 'supplier', 'dest': 'stock',
            },
        })
        return specs
