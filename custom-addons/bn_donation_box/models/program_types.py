from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._program_type_specs()
        specs.update({
            # the warehouse's Donation Box Operation Type (stock_warehouse.py)
            'donation_box': {
                'name': _('Donation Box'), 'code': 'internal', 'sequence_code': 'DBOX',
                'create_method': '_bn_donation_box_program_type',
            },
            'donation_box_repair': {
                'name': _('Donation Box Repair'), 'code': 'internal', 'sequence_code': 'DBR',
                'src': None, 'dest': 'stock',
            },
        })
        return specs
