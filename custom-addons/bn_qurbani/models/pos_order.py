from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)

        for order in orders:
            product_list = []

            for line in order.lines:
                product = line.product_id

                # Check both conditions
                if product.is_livestock and product.type == 'service':
                    product_list.append(product.id)
                

                # Find matching Qurbani Schedule
                schedule = self.env['qurbani.schedule'].search([
                    ('service_product_id', '=', product.id)
                ], limit=1)

                if schedule:
                    schedule.current_hissa += 1   # increment by 1

            # If list is not empty → create record
            if product_list:
                self.env['qurbani.order'].create({
                    'pos_order_id': order.id,
                    'receipt_number': order.pos_reference,
                    'product_ids': [(6, 0, product_list)],  # Many2many format
                })

        return orders