from odoo import api, models
from odoo import fields as odoo_fields


class POSOrder(models.Model):
    _inherit = 'pos.order'

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
        """Generate a DN number using available fields, mimicking the receipt format."""
        self.ensure_one()

        # 1. Branch code: try from company or a related branch field, else 'UNK'
        branch_code = 'UNK'
        if hasattr(self, 'branch_code') and self.branch_code:
            branch_code = self.branch_code
        elif self.company_id and self.company_id.name:
            # Use first 3 letters of company name as a code (like the receipt's 'branch_code')
            branch_code = self.company_id.name[:3].upper()

        # 2. Counter: may come from session or a custom field; fallback to 0
        counter = '0'
        if hasattr(self, 'counter') and self.counter:
            counter = str(self.counter)
        elif self.session_id and hasattr(self.session_id, 'counter'):
            counter = str(self.session_id.counter or 0)   # if session has a counter field

        # 3. Year: use order's date or today
        year = self.date_order.year if self.date_order else fields.Date.today().year

        # 4. POS order sequence: use last 4 digits of the order name (or pos_reference)
        pos_order_seq = '0000'
        order_name = self.name or self.pos_reference or ''
        # Extract numbers from the end of the name (e.g., 'POS-001234' -> '1234')
        import re
        numbers = re.search(r'(\d+)$', order_name)
        if numbers:
            seq = numbers.group(1)
            # Pad to 4 digits (or use as is)
            pos_order_seq = seq[-4:].zfill(4)  # take last 4, pad with zeros if shorter

        return f"{branch_code}-C{counter}-{year}-{pos_order_seq}"

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
