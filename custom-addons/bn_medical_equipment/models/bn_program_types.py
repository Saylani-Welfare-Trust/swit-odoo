from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'medical_equipment': {
                'name': _('Medical Equipment'), 'code': 'outgoing', 'sequence_code': 'ME',
                'src': 'stock', 'dest': 'bn_medical_equipment.medical_equipment_location',
            },
        })
        return specs
