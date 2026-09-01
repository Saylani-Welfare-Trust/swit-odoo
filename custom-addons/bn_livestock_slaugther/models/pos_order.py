from psycopg2 import IntegrityError
from odoo import api, models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'

    pos_order_seq = fields.Char(string='POS Order Sequence', help="Sequential number from POS")
    dn_number = fields.Char(string='DN Number', copy=False)

    @api.model
    def _process_order(self, order_data, draft=False, existing_order=False):
        if order_data.get('data'):
            data = order_data['data']
            if data.get('pos_order_seq'):
                self.pos_order_seq = data['pos_order_seq']
        order_id = super()._process_order(order_data, draft=draft, existing_order=existing_order)
        order = self.browse(order_id)
        if order and not order.dn_number:
            dn_number = order._compute_dn_number()
            order.write({
                'dn_number': dn_number,
                'source_document': dn_number,
            })
        return order_id

    def _get_branch_code(self):
        """Branch code is stored on hr.employee."""
        self.ensure_one()
        employee = self.employee_id or self.user_id.employee_id
        return employee.branch_code or 'UNK'

    def _compute_dn_number(self):
        """DN # = {branch_code}-C{counter}-{year}-{pos_order_seq}

        - branch_code: stored on hr.employee
        - counter:     stored on pos.config (via the session)
        - pos_order_seq: stored on this pos.order record
        """
        self.ensure_one()
        city_code = self._get_branch_code()
        counter = self.session_id.config_id.counter or '0'
        current_year = fields.Date.context_today(self).year
        pos_order_seq = self.pos_order_seq or '0000'
        return f"{city_code}-C{counter}-{current_year}-{pos_order_seq}"

    def _get_livestock_department_vals(self, product):
        product_markers = ' '.join(filter(None, [
            product.display_name,
            product.default_code,
            product.product_tmpl_id.name,
            product.categ_id.complete_name,
        ])).lower()

        if 'goat' in product_markers:
            return {'is_goat_depart': True}
        if 'cow' in product_markers:
            return {'is_meat_depart': True}
        return {}

    def _create_livestock_slaughter_records(self):
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for order in self:
            if order.state not in ('paid', 'done', 'invoiced'):
                continue

            livestock_lines = order.lines.filtered(
                lambda line: line.product_id.is_livestock and line.qty > 0
            )
            if not livestock_lines:
                continue

            existing_line_ids = set(slaughter_obj.search([
                ('pos_order_line_id', 'in', livestock_lines.ids),
            ]).mapped('pos_order_line_id').ids)

            if not order.dn_number:
                dn_number = order._compute_dn_number()
                order.write({
                    'dn_number': dn_number,
                    'source_document': dn_number,
                })

            reference = order.source_document or order.dn_number

            for line in livestock_lines:
                if line.id in existing_line_ids:
                    continue

                price = line.price_subtotal_incl or line.price_subtotal or line.price_unit * line.qty

                slaughter_vals = {
                    'product_id': line.product_id.id,
                    'donee_id': order.partner_id.id,
                    'pos_order_id': order.id,
                    'pos_order_line_id': line.id,
                    'quantity': int(line.qty),
                    'price': price,
                    'ref': reference,
                }
                slaughter_vals.update(order._get_livestock_department_vals(line.product_id))

                try:
                    with self.env.cr.savepoint():
                        slaughter_obj.create(slaughter_vals)
                except IntegrityError:
                    continue

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._create_livestock_slaughter_records()
        return orders

    def write(self, vals):
        result = super().write(vals)
        self._create_livestock_slaughter_records()
        return result


class POSOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped('order_id')._create_livestock_slaughter_records()
        return lines

    def write(self, vals):
        result = super().write(vals)
        self.mapped('order_id')._create_livestock_slaughter_records()
        return result
