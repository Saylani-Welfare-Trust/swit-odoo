from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'online_donation': {
                'name': _('Online Donation'), 'code': 'internal', 'sequence_code': 'OD',
                'src': 'stock', 'dest': 'bn_import_donation.online_donation_stock_location',
            },
        })
        return specs
