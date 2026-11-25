from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id, name, origin,
                               company_id, values):
        """A program confirming its sale order (context ``program_picking_type``,
        e.g. Microfinance) gets its own operation type of the warehouse on the
        delivery instead of the standard Delivery Orders type."""
        move_values = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)
        program = self.env.context.get('program_picking_type')
        warehouse = self.picking_type_id.warehouse_id
        if program and warehouse and self.picking_type_id.code == 'outgoing':
            move_values['picking_type_id'] = warehouse._program_type(program).id
        return move_values
