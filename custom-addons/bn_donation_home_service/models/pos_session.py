from odoo import models
from odoo.exceptions import ValidationError


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('is_livestock')
        result['search_params']['fields'].append('detailed_type')
        return result
    
    def _create_picking_at_end_of_session(self):
        self.ensure_one()

        picking_type = self.config_id.picking_type_id
        if not picking_type or not picking_type.default_location_dest_id:
            session_destination_id = self.env['stock.warehouse']._get_partner_locations()[0].id
        else:
            session_destination_id = picking_type.default_location_dest_id.id

        # ------------------------------------------------
        # Buckets
        # ------------------------------------------------
        lines_grouped_by_dest_location = {}
        dhs_orders_by_document = {}

        for order in self._get_closed_orders():
            # raise ValidationError(str(order))

            if order.company_id.anglo_saxon_accounting and order.is_invoiced or order.shipping_date:
                continue

            destination_id = order.partner_id.property_stock_customer.id or session_destination_id

            # 🔹 DHS Orders → separate picking
            if order.source_document and 'DHS' in order.source_document:
                if destination_id in dhs_orders_by_document:
                    dhs_orders_by_document[destination_id] |= order.lines
                else:
                    dhs_orders_by_document[destination_id] = order.lines
            else:
                if destination_id in lines_grouped_by_dest_location:
                    lines_grouped_by_dest_location[destination_id] |= order.lines
                else:
                    lines_grouped_by_dest_location[destination_id] = order.lines

        # ------------------------------------------------
        # NORMAL POS PICKINGS (UNCHANGED)
        # ------------------------------------------------
        for location_dest_id, lines in lines_grouped_by_dest_location.items():
            pickings = self.env['stock.picking']._create_picking_from_pos_order_lines(
                location_dest_id, lines, picking_type
            )
            pickings.write({
                'pos_session_id': self.id,
                'origin': self.name,
            })

        # ------------------------------------------------
        # DHS PICKINGS (SEPARATE)
        # ------------------------------------------------
        dhs_picking_type = self.env.ref(
            'bn_donation_home_service.donation_home_service_pos_stock_picking_type',
            raise_if_not_found=False
        )

        for location_dest_id, lines in dhs_orders_by_document.items():
            pickings = self.env['stock.picking']._create_picking_from_pos_order_lines(
                location_dest_id, lines, dhs_picking_type
            )
            pickings.write({
                'pos_session_id': self.id,
                'origin': self.name,
            })