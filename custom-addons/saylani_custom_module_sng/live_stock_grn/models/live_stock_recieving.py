# File: models/receive_by_weight_wizard.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class ReceiveByWeightLinee(models.Model):
    _name = 'receive.by.weight.line'
    _description = 'Receive by Weight Line'
    s_no = fields.Integer(string="S.no", store=True)


    wizard_id = fields.Many2one('receive.by.weight.wizard')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(string="Quantity",)
    weight = fields.Float(string="Weight (kg)")
    available_product_ids = fields.Many2many('product.product', compute='_compute_available_products')
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')

    @api.depends('wizard_id.picking_id')
    def _compute_allowed_product_ids(self):
        for line in self:
            picking = line.wizard_id.picking_id
            print('picking', picking)
            if picking:
                product_ids = picking.move_ids.mapped('product_id').ids
                line.allowed_product_ids = [(6, 0, product_ids)]
            else:
                line.allowed_product_ids = [(6, 0, [])]


class ReceiveByWeightWizardd(models.Model):
    _name = 'receive.by.weight.wizard'
    _description = 'Receive Products by Weight'

    picking_id = fields.Many2one('stock.picking', required=True, store=True)
    line_ids = fields.One2many('receive.by.weight.line', 'wizard_id', string="Lines")
    is_received = fields.Boolean(string="Is Received", default=False)

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        """Re-compute s_no for each line in display order."""
        for rec in self:
            # enumerate starts at 1
            for idx, line in enumerate(rec.line_ids, start=1):
                line.s_no = idx

    def action_save_only(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_receive(self):
        StockQuant = self.env['stock.quant']
        Product = self.env['product.product']
        AttributeValue = self.env['product.attribute.value']

        total_picking_qty = sum(self.picking_id.move_ids.mapped('product_uom_qty'))
        if len(self.line_ids) < total_picking_qty:
            raise UserError("Number of lines is less than total quantity in the picking. Please add more lines.")

        if len(self.line_ids) > total_picking_qty:
            raise UserError("Number of lines is greater than total quantity in the picking. Please remove lines.")

        # Step 1: Decrease original picking move quantities (base products)
        for move in self.picking_id.move_ids:
            product = move.product_id
            quantity = move.product_uom_qty

            if product and quantity > 0:
                StockQuant._update_available_quantity(
                    product,
                    self.picking_id.location_dest_id,
                    -quantity
                )

        # Step 2: Process each line of the wizard
        for line in self.line_ids:
            base_product = line.product_id
            weight = line.weight

            if not base_product or weight <= 0:
                raise UserError("Please provide a valid product and weight.")

            # Step 2a: Find other products with the same name
            matching_products = Product.search([
                ('name', '=', base_product.name),
                ('id', '!=', base_product.id)
            ])

            if not matching_products:
                raise UserError(f"No other products found with the same name as '{base_product.name}'.")

            # Step 2b: Filter to those with matching attribute values
            matched_variant = None
            for product in matching_products:
                for attr_line in product.product_template_attribute_value_ids:
                    attr = attr_line.product_attribute_value_id
                    if attr.from_kg <= weight <= attr.to_kg:
                        matched_variant = product
                        break
                if matched_variant:
                    break

            if not matched_variant:
                raise UserError(f"No variant found in range {weight} kg for product {base_product.display_name}.")

            # Step 3: Increase stock for the matched variant
            StockQuant._update_available_quantity(
                matched_variant,
                self.picking_id.location_dest_id,
                1  # One unit per line
            )

            # Step 4: Update quantity_done in matching move, if any
            related_moves = self.picking_id.move_ids.filtered(lambda m: m.product_id == matched_variant)
            if related_moves:
                for move in related_moves:
                    remaining_qty = move.product_uom_qty - move.quantity_done
                    if remaining_qty > 0:
                        move.quantity_done += 1
                        break
        self.is_received = True  # ✅ Mark as received

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_receive222(self):
        StockQuant = self.env['stock.quant']

        move_obj = self.env['stock.move']


        # Step 1: Decrease on-hand quantity of products in the picking
        for move in self.picking_id.move_ids:
            product = move.product_id
            quantity = move.product_uom_qty

            if product and quantity > 0:
                StockQuant._update_available_quantity(
                    product,
                    self.picking_id.location_dest_id,
                    -quantity  # Decrease original product stock
                )

        # Step 2: Increase on-hand quantity for products received via wizard
        for line in self.line_ids:
            product = line.product_id
            quantity = line.quantity

            if not product or quantity <= 0:
                raise UserError("Please provide a valid product and quantity.")

            # Increase quantity of the received product
            StockQuant._update_available_quantity(
                product,
                self.picking_id.location_dest_id,
                quantity
            )

            # Update quantity_done in related moves, if any
            related_moves = self.picking_id.move_ids.filtered(lambda m: m.product_id == product)
            if related_moves:
                qty_remaining = quantity
                for move in related_moves:
                    remaining_qty = move.product_uom_qty - move.quantity_done
                    if remaining_qty <= 0:
                        continue

                    qty_to_add = min(qty_remaining, remaining_qty)
                    move.quantity_done += qty_to_add
                    qty_remaining -= qty_to_add

                    if qty_remaining <= 0:
                        break
            else:
                # Optional: create a new move or skip
                continue

# File: models/stock_picking_inherit.py
from odoo import models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def open_receive_by_weight_wizard(self):
        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
            },
        }