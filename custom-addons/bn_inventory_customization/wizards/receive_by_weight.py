from odoo import models, fields, api
from odoo.exceptions import UserError


class ReceiveByWeight(models.TransientModel):
    _name = 'receive.by.weight'
    _description = "Receive By Weight"


    picking_id = fields.Many2one('stock.picking')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
        readonly=True,
    )

    line_ids = fields.One2many('receive.by.weight.line', 'receive_by_weight_id', string="Lines")

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

                unit_price = line.product_id.lst_price or 0.0

                total_amt += w * float(unit_price)

            rec.total_weight = total_w
            rec.bill_amount = total_amt

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        picking_id = self.env.context.get('default_picking_id')

        if picking_id:
            picking = self.env['stock.picking'].browse(picking_id)
            lines = []
            s_no = 1
            for move in picking.move_ids:
                print(">>> Processing move:", move.product_id.display_name, "qty:", move.product_uom_qty)
                for i in range(int(move.product_uom_qty)):
                    lines.append((0, 0, {
                        's_no': s_no,
                        'product_id': move.product_id.id,
                        'quantity': 1.0,
                    }))
                    s_no += 1
            res['line_ids'] = lines

        return res

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        """Re-compute s_no for each line in display order."""
        for rec in self:
            # enumerate starts at 1
            for idx, line in enumerate(rec.line_ids, start=1):
                line.s_no = idx

    def action_receive(self):
        StockQuant = self.env['stock.quant']
        StockMove = self.env['stock.move']

        # Sanity check
        total_picking_qty = sum(self.picking_id.move_ids.mapped('product_uom_qty'))
        if len(self.line_ids) != total_picking_qty:
            raise UserError(
                "Number of lines must be equal to total quantity in the picking."
            )

        # STEP 1: Remove stock of dummy purchase products
        for move in self.picking_id.move_ids:
            if move.product_id and float(move.product_uom_qty or 0.0) > 0.0:
                StockQuant._update_available_quantity(
                    move.product_id,
                    self.picking_id.location_dest_id,
                    -float(move.product_uom_qty)
                )

        # STEP 2: Add stock using selected variant from each line
        for line in self.line_ids:
            base_product = line.product_id        # dummy purchase product
            variant = line.livestock_product_id             # selected real variant
            weight = float(line.weight or 0.0)

            if not base_product:
                raise UserError("Product is missing on a line.")

            if not variant:
                raise UserError(
                    "Please select a variant for product '%s'." 
                    % base_product.display_name
                )

            if weight <= 0.0:
                raise UserError(
                    "Please provide a valid weight for product '%s'."
                    % base_product.display_name
                )

            # Increase stock for selected variant
            StockQuant._update_available_quantity(
                variant,
                self.picking_id.location_dest_id,
                1.0
            )

            # STEP 3: Handle stock.move creation / update
            related_moves = self.picking_id.move_ids.filtered(
                lambda m: m.product_id == variant
            )

            if related_moves:
                move = related_moves[0]
                move.write({
                    'product_uom_qty': move.product_uom_qty + 1.0,
                    'quantity': move.quantity + 1.0,
                })
            else:
                StockMove.create({
                    'name': variant.display_name,
                    'product_id': variant.id,
                    'product_uom_qty': 1.0,
                    'quantity': 1.0,
                    'product_uom': variant.uom_id.id,
                    'picking_id': self.picking_id.id,
                    'location_id': self.picking_id.location_id.id,
                    'location_dest_id': self.picking_id.location_dest_id.id,
                })

        # STEP 4: Update PO price (optional)
        if self.picking_id.purchase_id and self.bill_amount:
            purchase_order = self.picking_id.purchase_id
            if purchase_order.order_line:
                po_line = purchase_order.order_line[0]
                unit_price = float(self.bill_amount) / (po_line.product_qty or 1.0)
                po_line.write({'price_unit': unit_price})