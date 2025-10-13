from odoo import api, fields, models, _


class POSOrderModelInherit(models.Model):
    _inherit = 'pos.order'

    def _process_saved_order(self, draft):
        pos_order = super(POSOrderModelInherit, self)._process_saved_order(draft)
        for record in self:
            for order_line in record.lines:
                payment_method_ids = []
                for lines in record.payment_ids:
                    payment_method_ids.append(lines.payment_method_id.id)
                pos_payment_method = self.env['pos.payment.method'].sudo().search([('id', 'in', payment_method_ids), ('stock_in', '=', True)], limit=1)
                product_stock_move_config = self.env['product.stock.move.config'].sudo().search([], limit=1)
                if pos_payment_method:
                    vals = {
                        "name": self.env['ir.sequence'].next_by_code('product.stock.move.sequence'),
                        "partner_id": record.partner_id.id,
                        "location_id": product_stock_move_config.location_id.id,
                        "product_id": order_line.product_id.id,
                        "quantity": order_line.qty,
                        "state": 'draft',
                        "company_id": self.env.company.id,
                        "debit_account_id": product_stock_move_config.debit_account_id.id,
                        "credit_account_id": product_stock_move_config.credit_account_id.id,
                        'stock_picking_type_id': product_stock_move_config.stock_picking_type_id.id,
                        "journal_id": product_stock_move_config.journal_id.id,
                    }
                    product_stock_move = self.env['product.stock.move'].sudo().create(vals)
                    if product_stock_move:
                        product_stock_move.action_validate()
        return pos_order

