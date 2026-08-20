from odoo import api, models


class POSOrder(models.Model):
    _inherit = 'pos.order'

    def _create_livestock_slaughter_records(self):
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for order in self:
            if order.state not in ('paid', 'done', 'invoiced'):
                continue

            livestock_lines = order.lines.filtered(
                lambda line: line.product_id.is_livestock and line.qty > 0
            )

            for line in livestock_lines:
                existing_record = slaughter_obj.search([
                    ('pos_order_line_id', '=', line.id),
                ], limit=1)
                if existing_record:
                    continue

                reference = order.source_document or order.pos_reference or order.name
                price = line.price_subtotal_incl or line.price_subtotal or line.price_unit * line.qty

                slaughter_obj.create({
                    'product_id': line.product_id.id,
                    'donee_id': order.partner_id.id,
                    'pos_order_id': order.id,
                    'pos_order_line_id': line.id,
                    'quantity': int(line.qty),
                    'price': price,
                    'ref': reference,
                })

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._create_livestock_slaughter_records()
        return orders

    def write(self, vals):
        result = super().write(vals)
        self._create_livestock_slaughter_records()
        return result
