from odoo import api, models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'

    pos_order_seq = fields.Char(string='POS Order Sequence', help="Sequential number from POS")
    dn_number = fields.Char(string='DN Number', copy=False)

    @api.model
    def _process_order(self, order_data, draft=False, existing_order=False):
        order_id = super()._process_order(order_data, draft=draft, existing_order=existing_order)
        order = self.browse(order_id)
        if order and not order.dn_number:
            dn_number = order._compute_dn_number()
            vals = {'dn_number': dn_number}
            # keep the request a program order was made for (welfare,
            # medical equipment, qurbani ...)
            if not order.source_document:
                vals['source_document'] = dn_number
            order.write(vals)
        return order_id

    def _get_branch_code(self):
        """Branch code is stored on res.users (the cashier)."""
        self.ensure_one()
        return self._branch_code()

    def _compute_dn_number(self):
        """DN # = {branch_code}-C{counter}-{year}-{pos_order_seq}

        - branch_code:   the shop's Branch (pos.config / session)
        - counter:       stored on pos.config (via the session) - existing field, not redefined here
        - pos_order_seq: stored on this pos.order record
        """
        self.ensure_one()
        city_code = self._get_branch_code()
        counter = self.session_id.config_id.counter or 0
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
        if 'chicken' in product_markers:
            return {'is_chicken_depart': True}
        return {}

    def _paid_dhs(self):
        """The Donation Home Service this order pays: the POS gives the order its
        number as Source Document, and links it to the order once saved."""
        self.ensure_one()
        domain = [('pos_order_id', '=', self.id)]
        if self.source_document:
            domain = ['|', ('name', '=', self.source_document)] + domain
        return self.env['donation.home.service'].sudo().search(domain)

    def _create_livestock_slaughter_records(self):
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for order in self:
            if order.state not in ('paid', 'done', 'invoiced'):
                continue

            # Cash payments fall into livestock right away. Cheque and direct
            # deposit payments (both tracked through pos.cheque/cheque_state)
            # only do so once they are cleared - a bounced or cancelled
            # payment never reaches livestock.
            if order.pos_cheque_id and order.cheque_state != 'clear':
                continue

            livestock_lines = order.lines.filtered(
                lambda line: line.product_id.is_livestock and line.qty > 0
            )
            services = self.env['donation.home.service']
            if livestock_lines:
                # an order paying a Donation Home Service: the service makes the
                # records of its own products once Paid (donation.home.service)
                services = order._paid_dhs()
                service_products = services.donation_home_service_line_ids.product_id
                livestock_lines = livestock_lines.filtered(lambda line: line.product_id not in service_products)
            if not livestock_lines:
                continue

            if not order.dn_number:
                dn_number = order._compute_dn_number()
                vals = {'dn_number': dn_number}
                # an order paying a Donation Home Service keeps its number as Source Document
                if not services:
                    vals['source_document'] = dn_number
                order.write(vals)

            reference = order.source_document or order.dn_number

            for line in livestock_lines:
                vals = {
                    'product_id': line.product_id.id,
                    'donee_id': order.partner_id.id,
                    'pos_order_id': order.id,
                    'ref': reference,
                }
                vals.update(order._get_livestock_department_vals(line.product_id))
                total = line.price_subtotal_incl or line.price_subtotal or line.price_unit * line.qty
                slaughter_obj._create_for_source('pos_order_line_id', line, line.qty, total, vals)

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