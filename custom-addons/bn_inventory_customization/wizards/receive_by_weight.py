from odoo import models, fields, api
from odoo.exceptions import UserError


import logging
_logger = logging.getLogger(__name__)


class ReceiveByWeight(models.TransientModel):
    _name = 'receive.by.weight'
    _description = "Receive By Weight"

    picking_id = fields.Many2one('stock.picking', required=True, store=True)
    line_ids = fields.One2many('receive.by.weight.line', 'wizard_id', string="Lines")
    is_received = fields.Boolean(string="Is Received", default=False)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
        readonly=True,
    )

    total_weight = fields.Float(
        string='Total Weight (kg)',
        compute='_compute_totals',
        store=True,
    )
    bill_amount = fields.Monetary(
        string='Bill Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )

    @api.depends('line_ids.weight', 'line_ids.product_id')
    def _compute_totals(self):
        """Sum weights and compute bill as sum(weight * product_unit_price)."""
        for rec in self:
            total_w = 0.0
            total_amt = 0.0
            for line in rec.line_ids:
                w = float(line.weight or 0.0)
                total_w += w

                # choose the product price field you want to use for billing:
                # - lst_price = sales price
                # - standard_price = cost price
                # - product.seller_ids / vendor price would be more complex
                unit_price = line.product_id.lst_price or 0.0

                total_amt += w * float(unit_price)

            rec.total_weight = total_w
            rec.bill_amount = total_amt

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        _logger.debug("%s", (">>> default_get called, context:", self.env.context,))
        picking_id = self.env.context.get('default_picking_id')

        if picking_id:
            picking = self.env['stock.picking'].browse(picking_id)
            lines = []
            s_no = 1
            for move in picking.move_ids:
                qty = int(move.product_uom_qty or 0)
                _logger.debug("%s", (">>> Processing move:", move.product_id.display_name, "qty:", qty,))
                for _ in range(qty):
                    lines.append((0, 0, {
                        's_no': s_no,
                        'product_id': move.product_id.id,
                        'quantity': 1.0,
                    }))
                    s_no += 1
            res['line_ids'] = lines
        else:
            _logger.debug("%s", (">>> No picking_id in context",))
        return res

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        """Re-compute s_no for each line in display order."""
        for rec in self:
            for idx, line in enumerate(rec.line_ids, start=1):
                line.s_no = idx

    def action_save_only(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _match_variant(self, line):
        """The product variant a weighed unit is received as."""
        ProductTemplate = self.env['product.template']
        base_product = line.product_id  # dummy purchase product on the picking
        weight = float(line.weight or 0.0)
        livestock_variant = line.livestock_variant  # used to filter templates (not a variant record)

        if not base_product or weight <= 0.0:
            raise UserError("Please provide a valid product and weight for each line.")

        # Find templates that reference this base purchase product and match the livestock_variant
        templates = ProductTemplate.search([
            ('purchase_product', '=', base_product.id),
            ('livestock_variant', '=', livestock_variant.id if livestock_variant else False),
        ])

        if not templates:
            raise UserError(
                "No product template found that links purchase_product '%s' and livestock_variant '%s'."
                % (base_product.display_name, (livestock_variant.display_name if livestock_variant else 'N/A'))
            )

        # Among these templates, inspect their product variants and try to match by attribute value ranges
        matched_variant = None

        # STEP 1: Get all attribute values having weight ranges
        all_attr_vals = self.env['product.attribute.value'].search([
            ('from_kg', '!=', False),
            ('to_kg', '!=', False),
        ])

        # STEP 2: Find matching weight range
        weight_attr = None
        for attr_val in all_attr_vals:
            try:
                if float(attr_val.from_kg) <= weight <= float(attr_val.to_kg):
                    weight_attr = attr_val
                    break
            except Exception:
                continue

        if not weight_attr:
            raise UserError(f"No weight range found for weight {weight} kg")

        # STEP 3: Extract color from weight range name
        # Example: "7000 RED" → "red"
        weight_name = weight_attr.name.lower()
        color = weight_name.split()[-1]  # safest extraction
        # STEP 4: Find matching variant from templates
        for tmpl in templates:
            for variant in tmpl.product_variant_ids:


                variant_name = variant.display_name.lower()
                if color in variant_name:
                    matched_variant = variant
                    break

            if matched_variant:
                break


        # STEP 5: Final check
        if not matched_variant:
            raise UserError(
                f"No variant found matching color '{color}' for weight {weight} kg"
            )
        return matched_variant

    def action_receive(self):
        """Receive the weighed units: the receipt's placeholder (purchase product)
        moves are replaced by moves of the matching variants, linked to the same
        purchase order line. Stock enters (valued at the purchase price) when the
        receipt is validated - nothing is added to stock here."""
        self.ensure_one()
        picking = self.picking_id
        if self.is_received:
            raise UserError("These units are already received.")
        if picking.state in ('done', 'cancel'):
            raise UserError("Units can only be received on a receipt that is not done or cancelled.")

        # one line per unit
        total_picking_qty = sum(picking.move_ids.filtered(lambda m: m.product_id.check_stock).mapped('product_uom_qty'))
        if len(self.line_ids) < total_picking_qty:
            raise UserError("Number of lines is less than total quantity in the picking. Please add more lines.")
        if len(self.line_ids) > total_picking_qty:
            raise UserError("Number of lines is greater than total quantity in the picking. Please remove lines.")

        placeholder_moves = picking.move_ids.filtered(lambda m: m.product_id.check_stock)
        purchase_line_of = {move.product_id: move.purchase_line_id for move in placeholder_moves}

        # units per (variant, purchase line)
        units = {}
        for line in self.line_ids:
            variant = self._match_variant(line)
            key = (variant, purchase_line_of.get(line.product_id) or self.env['purchase.order.line'])
            units[key] = units.get(key, 0.0) + 1.0

        # the placeholder moves never entered stock: cancelled, then removed
        placeholder_moves._action_cancel()
        placeholder_moves.unlink()

        Move = self.env['stock.move']
        new_moves = Move
        for (variant, purchase_line), qty in units.items():
            new_moves |= Move.create({
                'name': variant.display_name,
                'product_id': variant.id,
                'product_uom_qty': qty,
                'product_uom': variant.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                # valued at the purchase price, counted as received on the purchase order
                'purchase_line_id': purchase_line.id or False,
                'company_id': picking.company_id.id,
            })
        new_moves._action_confirm()
        new_moves._action_assign()
        for move in new_moves:
            move.quantity = move.product_uom_qty

        # Finalize wizard/picking
        self.is_received = True
        self.picking_id.bill_amount = self.bill_amount

        # The bill amount is the price of the purchase line these units are
        # received for (the receipt is valued with it when it is validated)
        purchase_lines = self.env['purchase.order.line'].union(*[pl for (_v, pl) in units])
        if self.bill_amount and len(purchase_lines) == 1:
            purchase_lines.write({'price_unit': float(self.bill_amount) / (purchase_lines.product_qty or 1.0)})
        elif self.bill_amount and purchase_lines:
            picking.message_post(body="Bill amount %s not applied: the units belong to several purchase lines "
                                      "(%s); set their prices on the purchase order."
                                      % (self.bill_amount, ', '.join(purchase_lines.mapped('display_name'))))

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }