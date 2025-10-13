from odoo import models, fields, api, _

class PosSession(models.Model):
    _inherit = 'pos.session'

    microfinance_order_id = fields.Many2one('pos.order', 'Microfinance Order ID')

    def _compute_order_count(self):
        orders_data = self.env['pos.order']._read_group([('session_id', 'in', self.ids), ('is_microfinance_order', '=', False)], ['session_id'], ['__count'])
        sessions_data = {session.id: count for session, count in orders_data}
        for session in self:
            session.order_count = sessions_data.get(session.id, 0)


    def action_view_order(self):
        return {
            'name': _('Orders'),
            'res_model': 'pos.order',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('point_of_sale.view_pos_order_tree_no_session_id').id, 'tree'),
                (self.env.ref('point_of_sale.view_pos_pos_form').id, 'form'),
                ],
            'type': 'ir.actions.act_window',
            'domain': [('session_id', 'in', self.ids), ('is_microfinance_order', '=', False)],
        }


    def create_microfinance_payment(self, session_id, order_id, payment_method_id, amount):
        pos_payment = self.env['pos.payment'].create({
            'session_id': session_id,
            'pos_order_id': order_id,
            'payment_method_id': payment_method_id,
            'amount': amount
        })
        return pos_payment

    def create_entries_by_product(self, order_ids):
        entries = []

        for order in order_ids:
            if order.is_microfinance_order:
                continue
            order_payment_method = self.get_payment_method(order)
            if order.state != "done" and order.state != "invoiced" and not order.cheque_order:
                order.state = "done"

                for orderline in order.lines:
                    distribution = self.env['account.analytic.distribution.model']._get_distribution({
                        "product_id": orderline.product_id.id,
                        "product_categ_id": orderline.product_id.categ_id.id,
                        "partner_id": order.partner_id.id,
                        "partner_category_id": order.partner_id.category_id.ids,
                        "company_id": order.company_id.id,
                    })
                    print(distribution, 'distribution')
                    data = {
                        "move_type": "entry",
                        "ref": self.name,
                        "date": order.date_order,
                        "journal_id": 9,
                        "company_id": self.env.company.id,
                        "has_reconciled_entries": True
                    }
                    move_id = self.env['account.move'].create(data)
                    product_variant_id = orderline.product_id
                    credit_account_line = self.env['product.product.entry'].search(
                        [('product_id', '=', product_variant_id.id),
                         ('online_payment_method_id', '=', order_payment_method.id)], limit=1)
                    temp_list = []
                    data_line_credit = {
                        "move_id": move_id.id,
                        "account_id": credit_account_line.for_credit.id,
                        "name": credit_account_line.for_credit.name,
                        "credit": orderline.price_subtotal_incl,
                        "company_id": self.env.company.id,
                        "analytic_distribution": distribution
                    }
                    temp_list.append(data_line_credit)

                    data_line_debit = {
                        "move_id": move_id.id,
                        "account_id": credit_account_line.for_debit.id,
                        "name": credit_account_line.for_debit.name,
                        "debit": orderline.price_subtotal_incl,
                        "company_id": self.env.company.id,
                        "analytic_distribution": distribution
                    }
                    temp_list.append(data_line_debit)
                    move_id.line_ids.create(temp_list)
                    move_id.action_post()
                    entries.append(move_id.id)
                pp = order.write({
                    "account_move": move_id.id

                })
        self.write({"pos_moves_id": [(6, 0, entries)]})