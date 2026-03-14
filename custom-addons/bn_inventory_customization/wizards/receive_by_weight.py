from odoo import models, fields, api
from odoo.exceptions import UserError


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
        print(">>> default_get called, context:", self.env.context)
        picking_id = self.env.context.get('default_picking_id')

        if picking_id:
            picking = self.env['stock.picking'].browse(picking_id)
            lines = []
            s_no = 1
            for move in picking.move_ids:
                qty = int(move.product_uom_qty or 0)
                print(">>> Processing move:", move.product_id.display_name, "qty:", qty)
                for _ in range(qty):
                    lines.append((0, 0, {
                        's_no': s_no,
                        'product_id': move.product_id.id,
                        'quantity': 1.0,
                    }))
                    s_no += 1
            res['line_ids'] = lines
        else:
            print(">>> No picking_id in context")
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

    def action_receive(self):
        StockQuant = self.env['stock.quant']
        ProductTemplate = self.env['product.template']
        Product = self.env['product.product']

        # Sanity: number of wizard lines must equal total picking qty (one line per unit)
        total_picking_qty = sum(self.picking_id.move_ids.mapped('product_uom_qty'))
        if len(self.line_ids) < total_picking_qty:
            raise UserError("Number of lines is less than total quantity in the picking. Please add more lines.")
        if len(self.line_ids) > total_picking_qty:
            raise UserError("Number of lines is greater than total quantity in the picking. Please remove lines.")

        # STEP 1: Store and remove original (dummy) purchase product moves
        dummy_moves = self.picking_id.move_ids.filtered(lambda m: m.product_id.check_stock)
        
        # Decrease stock for dummy products that were added during validation
        for move in dummy_moves:
            if move.product_id and float(move.product_uom_qty or 0.0) > 0.0:
                StockQuant._update_available_quantity(
                    move.product_id,
                    self.picking_id.location_dest_id,
                    -float(move.product_uom_qty)
                )
        
        # Remove the dummy product moves from the picking
        dummy_moves.unlink()

        # STEP 2: for each wizard line, find real variant and increase its stock
        for line in self.line_ids:
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
            matched_attr_val = None
            for tmpl in templates:
                for variant in tmpl.product_variant_ids:
                    # product_template_attribute_value_ids links variant -> attribute value records
                    for ptav in variant.product_template_attribute_value_ids:
                        attr_val = ptav.product_attribute_value_id
                        # only consider attribute values that define from_kg/to_kg
                        if attr_val and (attr_val.from_kg is not None) and (attr_val.to_kg is not None):
                            try:
                                if float(attr_val.from_kg) <= weight <= float(attr_val.to_kg):
                                    matched_variant = variant
                                    matched_attr_val = attr_val
                                    break
                            except Exception:
                                # skip invalid values
                                continue
                    if matched_variant:
                        break
                if matched_variant:
                    break

            if not matched_variant:
                raise UserError(
                    "No matching variant found in range %s kg for product '%s' with livestock variant '%s'."
                    % (
                    weight, base_product.display_name, (livestock_variant.display_name if livestock_variant else 'N/A'))
                )

            # STEP 3: Increase stock for the matched variant (add 1 unit per wizard line)
            StockQuant._update_available_quantity(
                matched_variant,
                self.picking_id.location_dest_id,
                1.0
            )

            # STEP 4: Update a matching stock.move (if exists) or create a move for traceability and set quantity_done
            related_moves = self.picking_id.move_ids.filtered(lambda m: m.product_id == matched_variant)
            if related_moves:
                # add 1 to the first move that still has remaining qty
                found = False
                for move in related_moves:
                    remaining_qty = float(move.product_uom_qty or 0.0) - float(move.quantity or 0.0)
                    if remaining_qty > 0.0:
                        move.quantity += 1.0
                        found = True
                        break
                if not found:
                    # if all related moves are fully done, create a new move (keeps history consistent)
                    self.env['stock.move'].create({
                        'name': matched_variant.display_name,
                        'product_id': matched_variant.id,
                        'product_uom_qty': 1.0,
                        'quantity': 1.0,
                        'product_uom': matched_variant.uom_id.id,
                        'picking_id': self.picking_id.id,
                        'location_id': self.picking_id.location_id.id,
                        'location_dest_id': self.picking_id.location_dest_id.id,
                    })
            else:
                # No existing move for this variant — create one
                self.env['stock.move'].create({
                    'name': matched_variant.display_name,
                    'product_id': matched_variant.id,
                    'product_uom_qty': 1.0,
                    'quantity': 1.0,
                    'product_uom': matched_variant.uom_id.id,
                    'picking_id': self.picking_id.id,
                    'location_id': self.picking_id.location_id.id,
                    'location_dest_id': self.picking_id.location_dest_id.id,
                })

        # Finalize wizard/picking
        self.is_received = True
        self.picking_id.bill_amount = self.bill_amount

        # Optionally update related purchase order unit price based on bill_amount
        if self.picking_id.purchase_id and self.bill_amount:
            purchase_order = self.picking_id.purchase_id
            if purchase_order.order_line:
                po_line = purchase_order.order_line[0]
                unit_price = float(self.bill_amount) / (po_line.product_qty or 1.0)
                po_line.write({'price_unit': unit_price})

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }