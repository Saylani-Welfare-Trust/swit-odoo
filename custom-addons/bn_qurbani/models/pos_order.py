from odoo import models, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)

        for order in orders:
            qurbani_product_list = []

            for line in order.lines:
                product = line.product_id

                # ✅ Only livestock service products in Qurbani category
                if (
                    product.is_livestock
                    and product.type == 'service'
                    and product.categ_id
                    and 'qurbani' in product.categ_id.name.lower()
                ):
                    qurbani_product_list.append(product.id)

                    # -------------------------
                    # Update Qurbani Schedule
                    # -------------------------
                    schedule = self.env['qurbani.schedule'].search([
                        ('service_product_id', '=', product.id)
                    ], limit=1)
                    if schedule:
                        schedule.current_hissa += int(line.qty)

                    # -------------------------
                    # Create Livestock Slaughter Record
                    # -------------------------
                elif (
                    product.is_livestock
                ):
                    self.env['livestock.slaugther'].create({
                        'product_id': product.id,
                        'quantity': int(line.qty),
                        'ref': order.name,
                        'source_location_id': order.picking_type_id.default_location_src_id.id
                        if hasattr(order, 'picking_type_id') else False,
                    })

            # -------------------------
            # Create Qurbani Order
            # -------------------------
            if qurbani_product_list:
                self.env['qurbani.order'].create({
                    'pos_order_id': order.id,
                    'receipt_number': order.pos_reference,
                    'product_ids': [(6, 0, qurbani_product_list)],
                })

        return orders