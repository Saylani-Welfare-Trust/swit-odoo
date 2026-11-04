from odoo import _, api, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _bn_program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._bn_program_type_specs()
        specs.update({
            'dhs_gate_out': {
                'name': _('DHS Gate Out'), 'code': 'internal', 'sequence_code': 'DHS-GO',
                'src': 'stock', 'dest': 'bn_donation_home_service.gate_out_location',
            },
            'dhs_gate_in': {
                'name': _('DHS Gate In'), 'code': 'internal', 'sequence_code': 'DHS-GI',
                'src': 'bn_donation_home_service.gate_out_location', 'dest': 'bn_donation_home_service.gate_in_location',
            },
            'dhs_pos': {
                'name': _('DHS POS'), 'code': 'outgoing', 'sequence_code': 'DHS-POS',
                'src': 'bn_donation_home_service.gate_in_location', 'dest': 'customer',
            },
        })
        return specs
