from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # store the original base unit price (before multiplier)
    x_base_price = fields.Float(string="Base Unit Price")
    # store chosen to_kg multiplier
    to_kg_multiplier = fields.Float(string="To KG Multiplier", default=1.0)

    main_attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        related='product_id.product_tmpl_id.main_attribute_id',
        string="Main Attribute",
        help="The attribute used to calculate highest to_kg."
    )

    @api.onchange('product_id')
    def onchange_product_id(self):
        """Extend Odoo's product onchange: determine a reliable base price,
           pick highest to_kg on selected main_attribute_id,
           and set final price_unit = base * multiplier.
        """
        super().onchange_product_id()

        for line in self:
            if not line.product_id:
                line.x_base_price = 0.0
                line.to_kg_multiplier = 1.0
                continue

            if not line.product_id.check_stock:
                line.x_base_price = line.price_unit or 0.0
                line.to_kg_multiplier = 1.0
                continue

            # --- 1) Determine reliable base price ---
            base_price = 0.0
            partner = line.order_id.partner_id if line.order_id else False

            if partner:
                sellers = line.product_id.seller_ids.filtered(lambda s: s.display_name == partner)
                if sellers:
                    seller_prices = [s.price for s in sellers if s.price is not None]
                    if seller_prices:
                        base_price = min(seller_prices)

            if not base_price:
                if line.price_unit and line.price_unit not in (0.0, 1.0):
                    base_price = line.price_unit

            if not base_price:
                base_price = line.product_id.standard_price or line.product_id.list_price or 0.0

            line.x_base_price = float(base_price or 0.0)

            # --- 2) Highest to_kg only on main_attribute_id ---
            max_to_kg = 1.0
            if line.main_attribute_id:
                attr_values = self.env['product.attribute.value'].search([
                    ('attribute_id', '=', line.main_attribute_id.id)
                ])
                if attr_values:
                    max_to_kg = max(attr_values.mapped('to_kg') or [1.0])
                else:
                    max_to_kg = 1.0
            else:
                max_to_kg = 1.0
            line.to_kg_multiplier = float(max_to_kg or 1.0)

            # --- 3) Apply final unit price ---
            line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier)

    @api.onchange('product_qty')
    def _onchange_product_qty_reapply_multiplier(self):
        """When qty changes, reapply price_unit from saved base to prevent price drift.
           This avoids price_unit being reset to 1 or multiplied again incorrectly.
        """
        for line in self:
            if not line.product_id or not line.product_id.check_stock:
                continue
            # If we have a saved base price, reapply it
            if line.x_base_price:
                line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier)

    @api.onchange('price_unit')
    def _onchange_price_unit_store_base(self):
        """If user manually edits price_unit, update x_base_price accordingly so we keep
           consistent behavior (base = price_without_multiplier).
        """
        for line in self:
            if not line.product_id or not line.product_id.check_stock:
                continue
            if line.to_kg_multiplier and line.to_kg_multiplier != 1.0:
                # If user changes price_unit manually, store underlying base
                try:
                    base = float(line.price_unit) / float(line.to_kg_multiplier)
                except Exception:
                    base = float(line.price_unit)
                line.x_base_price = base
            else:
                line.x_base_price = float(line.price_unit or 0.0)

    def _compute_amount(self):
        """Ensure amounts are correct server-side (in case lines are created/updated by code).
           Recompute based on x_base_price and to_kg_multiplier when applicable, then call super to compute taxes & totals.
        """
        # Before calling super, ensure price_unit is consistent server-side
        for line in self:
            if line.product_id and line.product_id.check_stock:
                if line.x_base_price:
                    # apply base*multiplier as price_unit
                    line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier or 1.0)
                else:
                    # if no saved base, try to derive base from current price_unit
                    try:
                        base = float(line.price_unit) / float(line.to_kg_multiplier or 1.0)
                    except Exception:
                        base = float(line.price_unit or 0.0)
                    line.x_base_price = base
                    line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier or 1.0)

        # Now let Odoo compute subtotal/taxes normally
        super(PurchaseOrderLine, self)._compute_amount()



    def _prepare_account_move_line(self, move=False):
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)

        # res['price_unit'] = 0
        product_id = res['product_id']

        product = self.env['product.product'].browse(product_id)

        print('knkn', product.name)
        print('knkn', product.check_stock)

        if product and product.check_stock == True:
            print(self.move_ids.picking_id.bill_amount)
            bill_amt = self.move_ids.picking_id.bill_amount
            qty = res['quantity']
            res['price_unit'] = bill_amt/qty
        return res

