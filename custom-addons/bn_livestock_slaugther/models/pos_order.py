from odoo import api, models, fields
from odoo import fields as odoo_fields


class POSOrder(models.Model):
    _inherit = 'pos.order'
    
    branch_code = fields.Char(string='Branch Code', help="Short code for the branch")
    counter = fields.Char(string='Counter Number', help="POS session counter number")
    pos_order_seq = fields.Char(string='POS Order Sequence', help="Sequential number from POS")
    dn_number = fields.Char(string='DN Number', copy=False)
    
    @api.model
    def _process_order(self, order_data, draft=False, existing_order=False):
        # Extract custom fields from the frontend data
        if order_data.get('data'):
            data = order_data['data']
            if data.get('branch_code'):
                self.branch_code = data['branch_code']
            if data.get('counter'):
                self.counter = data['counter']
            if data.get('pos_order_seq'):
                self.pos_order_seq = data['pos_order_seq']
        # Call the original method to create/update the order
        return super()._process_order(order_data, draft=draft, existing_order=existing_order)

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
    
    def _get_dn_number(self):
        self.ensure_one()
        # These fields are now stored; provide fallbacks just in case
        city_code = self.branch_code or 'UNK'
        counter = self.counter or '0'
        year = self.date_order.year if self.date_order else fields.Date.today().year
        pos_order_seq = self.pos_order_seq or '0000'
        return f"{city_code}-C{counter}-{year}-{pos_order_seq}"

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

                # --- NEW: use generated DN number as reference ---
                reference = order._get_dn_number()

                price = line.price_subtotal_incl or line.price_subtotal or line.price_unit * line.qty

                slaughter_vals = {
                    'product_id': line.product_id.id,
                    'donee_id': order.partner_id.id,
                    'pos_order_id': order.id,
                    'pos_order_line_id': line.id,
                    'quantity': int(line.qty),
                    'price': price,
                    'ref': reference,   # now it's the DN number
                }
                slaughter_vals.update(order._get_livestock_department_vals(line.product_id))

                slaughter_obj.create(slaughter_vals)

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
